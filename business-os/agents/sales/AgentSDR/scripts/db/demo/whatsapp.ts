/**
 * Northwind's WhatsApp: two linked numbers (Jordan's and Lena's), about
 * seventy chats (campaign conversations, threads started from the phone, and
 * leads who wrote in first), two message campaigns, two call campaigns with
 * recorded calls and transcripts, and the follow-up messages reps opened
 * after calls.
 *
 * Written with the application's own functions where one fits: replies reach
 * the CRM through forwardWhatsappInboundToCrm / recordWhatsappOutboundInCrm
 * (with their real sent-at), and a call lead's CRM stage is set through
 * setLeadStage. History those functions would stamp "now" (chats, messages,
 * campaign rows, call sessions) is inserted directly with its own times.
 * Nothing here calls out: no Unipile, no R2, no model.
 *
 */

import { randomBytes, randomUUID, createHash } from "node:crypto";
import { eq, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { callCampaignContacts, callCampaigns, callMessages, callSessions } from "@/lib/calls/schema";
import { nextContactCallState, type ContactCallState } from "@/lib/calls/contactCallStatus";
import { setLeadStage } from "@/lib/calls/leadStage";
import type { CallTranscript, CampaignContactStage, ContactCallStatus } from "@/lib/calls/contract";
import { crmSubcategories, type CrmCategoryKey } from "@/lib/crm/schema";
import { lockCrmRecord, setRecordClassificationInTransaction, transitionWorkflowInTransaction } from "@/lib/crm/records";
import { withCrmTransaction } from "@/lib/crm/repository";
import { forwardWhatsappInboundToCrm, recordWhatsappOutboundInCrm } from "@/lib/whatsapp/crmBridge";
import type { WhatsappCampaignLeadStatus, WhatsappCampaignStep } from "@/lib/whatsapp/campaigns/contract";
import {
  whatsappAccounts,
  whatsappCampaignAccounts,
  whatsappCampaignLeads,
  whatsappCampaignSends,
  whatsappCampaigns,
  whatsappChats,
  whatsappMessages,
} from "@/lib/whatsapp/schema";
import { currentOrganizationId } from "@/lib/tenancy/scope";
import { REPLY_MIX, TEAM, type ReplyIntent } from "./content";
import { DAY, HOUR, MINUTE, count, createRng, type Rng, daysAgo, replyText, workTime, type DemoContext, type DemoPerson } from "./context";

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

type Rep = "jordan" | "lena";
const REPS: Rep[] = ["jordan", "lena"];

const plusMin = (d: Date, minutes: number) => new Date(d.getTime() + minutes * MINUTE);
const plusHours = (d: Date, hours: number) => new Date(d.getTime() + hours * HOUR);

/** The same day (or the next working day) at a random working-hours moment. */
function atBiz(ctx: DemoContext, d: Date): Date {
  const x = new Date(d);
  const dow = x.getUTCDay();
  if (dow === 6) x.setUTCDate(x.getUTCDate() + 2);
  if (dow === 0) x.setUTCDate(x.getUTCDate() + 1);
  x.setUTCHours(ctx.rand.int(13, 21), ctx.rand.int(0, 59), ctx.rand.int(0, 59), 0);
  return x;
}

/** A moment that is plausible for a chat message: moved forward out of the small hours and off weekends. */
function humanize(ctx: DemoContext, d: Date): Date {
  const x = new Date(d);
  if (x.getUTCHours() < 12) x.setUTCHours(ctx.rand.int(12, 14), ctx.rand.int(0, 59), ctx.rand.int(0, 59), 0);
  else if (x.getUTCHours() >= 23) {
    x.setUTCDate(x.getUTCDate() + 1);
    x.setUTCHours(ctx.rand.int(13, 15), ctx.rand.int(0, 59), ctx.rand.int(0, 59), 0);
  }
  const dow = x.getUTCDay();
  if (dow === 6) x.setUTCDate(x.getUTCDate() + 2);
  if (dow === 0) x.setUTCDate(x.getUTCDate() + 1);
  return x;
}

const digitsOf = (phone: string) => phone.replace(/\D/g, "");
const preview = (body: string) => {
  const text = body.replace(/\s+/g, " ").trim();
  return text.length > 200 ? `${text.slice(0, 199)}…` : text;
};
const sha256 = (value: string) => createHash("sha256").update(value).digest("hex");

async function insertInBatches<T>(rows: T[], size: number, insert: (batch: T[]) => Promise<unknown>) {
  for (let i = 0; i < rows.length; i += size) await insert(rows.slice(i, i + size));
}

// ---------------------------------------------------------------------------
// Chat copy
// ---------------------------------------------------------------------------

type Beat = { who: "R" | "L"; text: string; gap: [number, number] };
const R = (text: string, min = 4, max = 60): Beat => ({ who: "R", text, gap: [min, max] });
const L = (text: string, min = 3, max = 120): Beat => ({ who: "L", text, gap: [min, max] });

/** What happens after a lead's first reply, by what the reply meant. {lead} {rep} {repl} {company} {industry} {email}. */
const FOLLOW: Partial<Record<ReplyIntent, Beat[][]>> = {
  "Meeting Requested": [
    [
      R("Great, thanks {lead}! I can do Thursday 3pm or Friday 10am, whichever suits you. My calendar is here if that's easier: cal.northwind.example/{repl}", 6, 95),
      L("Thursday 3pm works", 4, 140),
      R("Booked ✅ invite is on its way. Talk Thursday!", 2, 12),
    ],
    [
      R("Appreciate it {lead}. 30 minutes is plenty, I'll keep it tight. Does Tuesday at 11 work?", 8, 120),
      L("Tuesday 11 is fine, send the invite over", 10, 200),
      R("Done 👍 You'll see it in your inbox in a minute", 2, 15),
      L("Got it, thanks", 3, 90),
    ],
    [
      R("Perfect, here's a link so you can pick a time that suits you: cal.northwind.example/{repl}/intro", 5, 80),
      R("I'll have a short walkthrough ready, nothing heavy", 1, 3),
      L("Booked for Wednesday. Thanks!", 30, 600),
      R("Excellent, speak Wednesday 🙌", 3, 40),
    ],
  ],
  "Demo Request": [
    [
      R("Happy to! I'll show the WhatsApp and LinkedIn side live. How about Wednesday at 2pm? About 25 minutes.", 6, 90),
      L("Wednesday works. Can my ops lead join too?", 8, 160),
      R("Of course, forward her the invite when it lands and I'll add her", 3, 30),
      L("Will do 👍", 2, 60),
      R("Invite sent ✅ See you both Wednesday.", 10, 120),
    ],
    [
      R("Absolutely. So I tailor it: how many reps would use it, and which channels matter most?", 6, 100),
      L("About 8 SDRs, mostly LinkedIn and email, a bit of WhatsApp", 10, 240),
      R("Got it. I'll focus on the shared inbox and reply classification. Does Thursday at 11 work?", 4, 40),
      L("Thursday 11 works", 5, 120),
      R("Booked ✅ Invite coming now", 2, 10),
    ],
  ],
  "Information Requested": [
    [
      R("Sure! The Team plan is $129 per seat per month, and there's a free 14-day pilot with two seats if you'd like to try it first. I'll send the one-pager over 📎", 6, 80),
      L("Could you drop it here instead of email?", 8, 180),
      R("Of course, here it is: northwind.example/signal-overview.pdf", 2, 10),
      L("Perfect, thank you. I'll share it with the team", 20, 300),
      R("Happy to help. I'll check back Thursday to see what they think 👍", 5, 90),
    ],
    [
      R("Good question. Setup usually takes an afternoon: connect your CRM, pick the lists to score, and the first weekly list lands the next Monday.", 8, 100),
      L("That's quicker than I expected", 6, 120),
      R("Most teams say the same. Want me to walk you through it on a 15 min call?", 3, 30),
      L("Maybe next week", 15, 240),
      R("No problem, I'll ping you Monday 👍", 4, 60),
    ],
    [
      R("Yes, two-way sync with HubSpot and Salesforce, and alerts into Slack. Overview here: northwind.example/integrations", 6, 70),
      L("Great, we use HubSpot", 5, 90),
      R("Then it's a good fit. Want a quick look at the HubSpot sync on a call?", 3, 25),
      L("Sure, later this week", 10, 200),
      R("How about Thursday at 11?", 4, 60),
      L("Works for me", 3, 80),
      R("Booked ✅", 2, 10),
    ],
  ],
  "Case Study": [
    [
      R("Absolutely. Brightloop is the closest example: 6 SDRs, first meetings went from 38 to 81 a month in one quarter. Write-up here: northwind.example/brightloop 📎", 6, 90),
      L("Interesting, will have a read", 10, 200),
      R("Great. I can also dig out a {industry} example if that's more useful", 4, 40),
      L("Yes please", 5, 120),
      R("I'll send one tomorrow 👍", 3, 40),
    ],
  ],
  "Trial Requested": [
    [
      R("Yes! Two seats free for 14 days, one campaign, no card needed. Can you share your work email so I can set up the workspace?", 5, 70),
      L("{email}", 6, 120),
      R("Got it, invite sent ✅ Shout if anything's unclear", 6, 60),
      L("Thanks!", 3, 90),
    ],
    [
      R("We can do that. A two-seat pilot on one campaign is the usual setup, 14 days, free. Who should I add?", 5, 80),
      L("Me and one of my reps, I'll send her details later today", 10, 220),
      R("Perfect, I'll set up the workspace in the meantime 👍", 4, 40),
    ],
  ],
  "Not Required Right Now": [
    [R("Totally understand, {lead}. I'll check back in a couple of months. Thanks for letting me know 🙏", 10, 180), L("Thanks, appreciate it", 5, 200)],
    [R("No problem at all, thanks for the quick answer. I'll leave you in peace until next quarter 🙂", 10, 240)],
  ],
  "Already Using a Tool — Not Required": [
    [R("Makes sense, thanks for the quick reply! Signal usually sits in front of a sequencer rather than replacing it, so if that ever becomes interesting I'm around.", 10, 180), L("Will keep it in mind", 8, 300)],
    [R("Understood, thanks {lead}. All the best with it!", 10, 200)],
  ],
  "Connected to Different POC": [
    [
      R("Thanks {lead}, that's really helpful. I'll reach out to them and mention you pointed me over 🙏", 8, 150),
      L("Great, I'll let them know to expect your message", 10, 240),
    ],
  ],
  "Left Company": [[R("No worries, thanks for letting me know. Good luck with what's next!", 10, 200)]],
  "Do Not Contact": [[R("Understood, sorry to bother you {lead}. I've removed your number and won't message again.", 5, 90)]],
  Other: [
    [
      R("Sorry for the surprise, {lead}! I'm {rep} from Northwind. I found {company} while looking at {industry} sales teams and thought Signal might help. Happy to drop it if it's not relevant.", 6, 90),
      L("OK, send me some info", 8, 200),
      R("Sure, here's a short overview: northwind.example/signal-overview.pdf", 3, 30),
    ],
  ],
};

type OrganicScript = {
  /** "lead": the lead wrote first; "rep": the rep opened it from their phone. */
  starter: "lead" | "rep";
  intent: ReplyIntent | null;
  day: number;
  rep: Rep;
  beats: Beat[];
  /** Rep messages sent from the phone rather than the Messages tab. */
  phoneRep: number;
};

const ORGANIC: OrganicScript[] = [
  {
    starter: "lead", intent: "Demo Request", day: 71, rep: "jordan", phoneRep: 0.25,
    beats: [
      L("Hi, is this Northwind? I saw Signal mentioned in a sales ops Slack community", 0, 0),
      R("Hi {lead}! Yes it is 🙂 Jordan here. What caught your eye?", 4, 25),
      L("We're a team of 9 reps and our research process is a mess. Does Signal work with HubSpot?", 6, 40),
      R("It does, two-way sync on the Team plan. Contacts, companies and activity all flow through.", 3, 20),
      L("Nice. Could I get a demo? Preferably with our sales ops person", 8, 60),
      R("Sure! How's Thursday at 2pm ET? About 30 min", 3, 25),
      L("Let me check with her and confirm", 5, 40),
      L("She's in, 2pm Thursday works for both of us", 120, 320),
      R("Great, sending the invite now. Anything specific you want covered?", 10, 80),
      L("Mostly how accounts get scored and how the alerts work", 6, 45),
      R("Perfect, I'll build the demo around that 👍 Talk Thursday!", 3, 20),
    ],
  },
  {
    starter: "lead", intent: "Information Requested", day: 46, rep: "lena", phoneRep: 0.4,
    beats: [
      L("Hey Lena, started the trial yesterday. Connected HubSpot but no accounts are showing up in the dashboard", 0, 0),
      R("Hi {lead}! Thanks for trying it. First syncs usually take 10-15 minutes. Did you pick which HubSpot lists to import?", 6, 40),
      L("I think so? It says Connected but 0 accounts", 5, 30),
      R("That's the list step. Settings → Integrations → HubSpot → Import lists, then tick at least one", 3, 15),
      R("I'll send you a quick screen recording as well, one sec", 1, 2),
      R("Just sent it to your email 👍", 6, 14),
      L("Found it, I hadn't ticked any 🤦 Importing now", 8, 40),
      L("OK 1,240 accounts are in. Nice!", 20, 40),
      R("Brilliant 🎉 Scores take a few minutes to fill in. Tell me if anything looks off", 5, 30),
      L("Will do. One more thing, can the weekly priority list go to Slack?", 30, 240),
      R("Yes, Settings → Notifications → Slack. Takes about a minute", 4, 25),
    ],
  },
  {
    starter: "lead", intent: "Trial Requested", day: 58, rep: "jordan", phoneRep: 0.3,
    beats: [
      L("Hi, got your number from the website. Is there a way to try Signal before we commit?", 0, 0),
      R("Hey {lead}, yes! We run a 14-day pilot, two seats free and one campaign, no card needed", 5, 40),
      L("Perfect. What do you need from me to start?", 5, 35),
      R("Just your work email and the CRM you use. I'll set the workspace up today", 3, 20),
      L("It's HubSpot. Email is {email}", 6, 40),
      R("Got it, invite is on its way. You'll see it in a few minutes 👍", 4, 20),
    ],
  },
  {
    starter: "lead", intent: "Meeting Requested", day: 33, rep: "lena", phoneRep: 0.2,
    beats: [
      L("Hi Lena, we spoke briefly at the SaaS North mixer last week. Could we find 20 min to talk about Signal?", 0, 0),
      R("Of course! Great to hear from you {lead}. I have Tuesday 10:30 or Wednesday 4pm free", 8, 60),
      L("Wednesday 4pm please", 10, 90),
      R("Locked in ✅ I'll send the invite. Looking forward to it", 3, 25),
      L("Thanks, see you then 👍", 4, 40),
      R("See you Wednesday 🙌", 3, 30),
    ],
  },
  {
    starter: "lead", intent: "Information Requested", day: 21, rep: "jordan", phoneRep: 0.2,
    beats: [
      L("Hello, could you tell me what the Team plan costs for 12 seats?", 0, 0),
      R("Hi {lead}! Team is $129 per seat per month, so $1,548 a month for 12. Annual billing takes 15% off", 6, 35),
      L("And does that include the shared inbox?", 4, 30),
      R("Yes, shared inbox, CRM sync and up to 25,000 accounts", 2, 15),
      L("Thanks, I'll take this to our CFO and come back to you", 10, 60),
      R("Sounds good. Want me to send a one-pager you can forward? 📎", 3, 20),
      L("Yes please", 5, 40),
      R("Sent ✅ Check your email in a minute", 2, 12),
    ],
  },
  {
    starter: "lead", intent: "Case Study", day: 3, rep: "lena", phoneRep: 0,
    beats: [
      L("Hi Lena, quick one. Do you have a case study from a {industry} company like ours?", 0, 0),
      L("Ideally 100-200 employees", 3, 6),
    ],
  },
  {
    starter: "rep", intent: "Meeting Requested", day: 77, rep: "jordan", phoneRep: 1,
    beats: [
      R("Hi {lead}, Jordan from Northwind. Great meeting you at the Pipeline Summit yesterday! As promised, here's the link to book some time: cal.northwind.example/jordan", 0, 0),
      L("Thanks Jordan, good chatting. Let me look at calendars", 120, 300),
      L("How about Friday at 1pm?", 600, 1200),
      R("Friday 1pm works. Sending the invite now", 10, 90),
      L("Received. See you then", 5, 60),
      R("Thanks for your time today {lead}! Here's the deck we went through: northwind.example/signal-deck.pdf", 4320, 4400),
      L("Got it, thanks. I'll circulate it internally", 20, 200),
      R("Perfect, shout if anyone has questions", 5, 60),
    ],
  },
  {
    starter: "rep", intent: "Information Requested", day: 64, rep: "lena", phoneRep: 0.7,
    beats: [
      R("Hi {lead}, it's Lena from Northwind. Following up on your question about data privacy. Short version: SOC 2 Type II, and each customer's data sits in its own workspace", 0, 0),
      R("I can send the security pack and DPA if useful", 1, 2),
      L("Yes please, our security team will want that", 40, 400),
      R("Sent to {email} just now 📎", 5, 60),
      L("Got it. Their review usually takes about 2 weeks", 60, 600),
      R("No problem, I'll check in after. Shout if they have questions", 5, 50),
    ],
  },
  {
    starter: "rep", intent: "Not Required Right Now", day: 52, rep: "lena", phoneRep: 1,
    beats: [
      R("Hi {lead}, Lena from Northwind. You mentioned Q4 planning last week, wanted to check whether Signal is still on the table?", 0, 0),
      L("Hi Lena. We've paused all new tooling until January, sorry", 90, 700),
      R("Totally fine, thanks for being upfront! I'll reach out early January 🙂", 10, 120),
      L("Appreciate it", 5, 120),
      R("🙏", 2, 20),
    ],
  },
  {
    starter: "rep", intent: "Connected to Different POC", day: 38, rep: "jordan", phoneRep: 0.8,
    beats: [
      R("Hi {lead}, Jordan from Northwind. Was told you own sales tooling at {company}, is that right?", 0, 0),
      L("Not anymore, that moved to Marcus in RevOps last quarter", 40, 500),
      L("I'll introduce you, one sec", 2, 5),
      R("That would be great, thank you {lead}!", 3, 30),
      L("Done, I've copied him on an email to you", 20, 120),
      R("Got it, thank you. I'll reach out to him today 🙏", 5, 60),
    ],
  },
  {
    starter: "rep", intent: "Demo Request", day: 29, rep: "jordan", phoneRep: 0.7,
    beats: [
      R("Hey {lead}, Jordan here (Northwind). Thanks for the call earlier. Just sent the deck 👍", 0, 0),
      L("Got it, thanks. This looks like what we've been missing", 30, 240),
      L("Can you demo it for our two team leads next week?", 2, 8),
      R("Absolutely. Tuesday or Thursday, afternoons work best for me", 5, 40),
      L("Thursday 3pm?", 10, 90),
      R("Thursday 3pm it is. I'll send the invite to you, and I'll add them if you share their emails", 3, 25),
      L("Will do, thank you!", 6, 60),
      R("Invite sent ✅", 120, 400),
      L("Received 🙌", 5, 80),
      R("👍", 2, 20),
    ],
  },
  {
    starter: "rep", intent: "Meeting Requested", day: 4, rep: "lena", phoneRep: 1,
    beats: [
      R("Hi {lead}, Lena from Northwind. Thanks for connecting on LinkedIn! Would a quick 20 min intro next week make sense?", 0, 0),
      L("Hi Lena, yes happy to. Tuesday morning?", 90, 400),
    ],
  },
  {
    starter: "rep", intent: null, day: 41, rep: "jordan", phoneRep: 1,
    beats: [
      R("Hi {lead}, Jordan from Northwind. We spoke on the call Tuesday, here's my calendar for the follow-up: cal.northwind.example/jordan", 0, 0),
      R("No rush at all, just bumping this in case it got buried 🙂", 2600, 3400),
    ],
  },
  {
    starter: "rep", intent: null, day: 8, rep: "lena", phoneRep: 1,
    beats: [R("Hi {lead}, Lena from Northwind. Sorry I missed you on the call just now! Is there a better time to reach you?", 0, 0)],
  },
  {
    starter: "lead", intent: "Trial Requested", day: 2, rep: "jordan", phoneRep: 0,
    beats: [
      L("Hi Jordan, a colleague mentioned you. Could we pilot Signal with two of our SDRs?", 0, 0),
      L("We're on HubSpot if that matters", 4, 9),
    ],
  },
  {
    starter: "lead", intent: "Information Requested", day: 1, rep: "lena", phoneRep: 0,
    beats: [L("Hello, what's the difference between Starter and Team?", 0, 0)],
  },
];

/** Replies a rep would answer by hand (the CRM module answers the rest). */
const HANDLED_INTENTS = new Set<ReplyIntent>([
  "Meeting Requested", "Demo Request", "Information Requested", "Case Study", "Trial Requested",
  "Not Required Right Now", "Already Using a Tool — Not Required", "Connected to Different POC",
]);

/** What a rep types from their phone beside a campaign message. */
const PHONE_NUDGES = [
  "{lead}, in case it's easier I can send a 60-second walkthrough video instead of a call 🙂",
  "Happy to do this over a quick voice note if that suits you better, {lead}",
  "P.S. no pressure at all, just curious how {company} handles account research today",
  "Saw you're hiring on the sales side, which is partly why I reached out. Worth a chat?",
  "If WhatsApp isn't your channel I can move this to email, just say 👍",
  "{lead}, one thing I forgot: there's a free two-seat pilot if you'd rather test it than talk",
  "Quick one: are you the right person for sales tooling at {company}? If not, a pointer would be great 🙏",
];

/** Step bodies use the app's spin text, {A|B|C}: each lead gets one of the options. */
const CAMPAIGN_A_STEPS: WhatsappCampaignStep[] = [
  {
    id: "a-intro",
    body: "{Hi|Hey} {{firstName}} 👋 {Northwind here.|This is the Northwind team.|Quick intro from Northwind.} We built Signal to tell sales teams which accounts to work each week and why. {Teams like Brightloop cut research time by ~70%.|Brightloop's reps cut their research time by about 70%.|Most teams cut research time by more than half.} {Mind if I send a 2-minute overview?|Want me to send a 2-minute overview?|Worth a quick look?}",
    delayHours: 0,
  },
  {
    id: "a-followup",
    body: "{Quick follow-up in case this got buried|Bumping this up in case it slipped past you|Circling back in case my last note got buried}, {{firstName}}. {Happy to show you how Signal would work for your team, or just send the one-pager.|Want a 2-minute demo, or should I just send the one-pager?|I can send the one-pager or walk you through it, whichever is easier.}",
    delayHours: 48,
  },
  {
    id: "a-breakup",
    body: "{Last note from me|Final nudge from me|Last one, I promise}, {{firstName}}. {I don't want to clutter your chat.|Not going to keep pinging you.|I'll leave it here.} {If outbound planning comes up, I'm one message away 🙂|Ping me whenever outbound planning comes up 🙂|If priorities change, just say the word 🙂}",
    delayHours: 96,
  },
];

const CAMPAIGN_B_STEPS: WhatsappCampaignStep[] = [
  {
    id: "b-sorry",
    body: "{Hi|Hey} {{firstName}}, {sorry we missed you at last week's webinar on running outbound across channels|we missed you at the outbound webinar last week}. {Want me to send the recording and the 1-page playbook we covered?|Shall I send the replay and the 1-page playbook?|Happy to send the recording plus the playbook if useful.}",
    delayHours: 0,
  },
  {
    id: "b-replay",
    body: "{Hey|Hi} {{firstName}}, {resurfacing the replay in case it's useful|here's the replay again in case it's useful}: northwind.example/webinar-replay. {Happy to answer questions once you've watched 👍|Tell me what you think once you've seen it 👍|Shout if anything's unclear after you watch.}",
    delayHours: 72,
  },
];

// ---------------------------------------------------------------------------
// Plans (everything is decided in memory first, then written)
// ---------------------------------------------------------------------------

type PlannedMsg = {
  dir: "inbound" | "outbound";
  origin: "lead" | "agentsdr" | "phone";
  body: string;
  at: Date;
  /** The campaign send this message is. */
  sendId?: string;
  callSessionId?: string;
};

type ChatPlan = {
  person: DemoPerson;
  rep: Rep;
  msgs: PlannedMsg[];
  /** What the lead's messages add up to, when there are any. */
  intent: ReplyIntent | null;
  unread: number;
  fromCampaign: boolean;
  /**
   * The rep has already answered and the thread was worked by hand: it is
   * recorded in the CRM and classified here. Every other chat the lead wrote
   * in ends with the lead's message, handed to the CRM module (a DemoReply)
   * to classify, draft for and answer.
   */
  handled: boolean;
};

type SendPlan = { id: string; step: number; stepId: string; at: Date; body: string; status: "sent" | "failed"; error: string | null };

type LeadPlan = {
  id: string;
  person: DemoPerson;
  rep: Rep;
  enrolledAt: Date;
  status: WhatsappCampaignLeadStatus;
  currentStep: number;
  nextSendAt: Date | null;
  lastSentAt: Date | null;
  repliedAt: Date | null;
  lastError: string | null;
  attempts: number;
  sends: SendPlan[];
  chat: ChatPlan | null;
};

function fillText(text: string, person: DemoPerson, rep: Rep): string {
  return text
    .replaceAll("{lead}", person.firstName)
    .replaceAll("{rep}", TEAM[rep].first)
    .replaceAll("{repl}", TEAM[rep].first.toLowerCase())
    .replaceAll("{company}", person.company.name)
    .replaceAll("{industry}", person.company.industry)
    .replaceAll("{email}", person.email);
}

function renderStep(body: string, person: DemoPerson, rand: Rng): string {
  const spun = body.replace(/\{([^{}]*\|[^{}]*)\}/g, (_m, inner: string) => rand.pick(inner.split("|")));
  return spun.replaceAll("{{firstName}}", person.firstName).replaceAll("{{company}}", person.company.name);
}

export async function seedWhatsapp(shared: DemoContext): Promise<void> {
  // Its own random stream: what the other modules drew must not change this module's story.
  const ctx: DemoContext = { ...shared, rand: createRng(Number(process.env.DEMO_WHATSAPP_SEED) || 9) };
  const org = currentOrganizationId();
  const now = ctx.now;
  const rand = ctx.rand;

  // Sends from one number are never closer than 10 s (the guardrail the real sender obeys).
  const taken: Record<Rep, Set<number>> = { jordan: new Set(), lena: new Set() };
  const spaced = (rep: Rep, t: Date): Date => {
    let at = t;
    const clash = (x: Date) => {
      const s = Math.floor(x.getTime() / 1000);
      for (let k = -10; k <= 10; k++) if (taken[rep].has(s + k)) return true;
      return false;
    };
    while (clash(at)) at = new Date(at.getTime() + rand.int(11, 40) * 1000);
    taken[rep].add(Math.floor(at.getTime() / 1000));
    return at;
  };

  // --- who is where -------------------------------------------------------
  const shuffled = rand.shuffle(ctx.pools.whatsapp);
  const A_COUNT = 36;
  const B_COUNT = 22;
  const peopleA = shuffled.slice(0, A_COUNT);
  const peopleB = shuffled.slice(A_COUNT, A_COUNT + B_COUNT);
  const peopleOrganic = shuffled.slice(A_COUNT + B_COUNT, A_COUNT + B_COUNT + ORGANIC.length);
  const peopleRest = shuffled.slice(A_COUNT + B_COUNT + ORGANIC.length);

  // --- campaign plans -----------------------------------------------------
  const chatPlans: ChatPlan[] = [];
  const leadPlans: { A: LeadPlan[]; B: LeadPlan[] } = { A: [], B: [] };

  let oooSeen = 0;
  const followBeats = (intent: ReplyIntent): Beat[] => {
    const variants = FOLLOW[intent];
    return variants && variants.length ? rand.pick(variants) : [];
  };

  /**
   * The lead's reply, and, when the thread is worked by hand, what came after
   * it as far as `now` allows. Otherwise the thread ends at the reply.
   */
  function appendReplyThread(plan: ChatPlan, replyAt: Date, intent: ReplyIntent, handled: boolean) {
    const person = plan.person;
    plan.intent = intent;
    plan.msgs.push({ dir: "inbound", origin: "lead", body: replyText(ctx, intent, "short", person, TEAM[plan.rep].first), at: replyAt });
    if (!handled) return;
    let prev = replyAt;
    for (const beat of followBeats(intent)) {
      const t = humanize(ctx, plusMin(prev, rand.int(beat.gap[0], beat.gap[1])));
      if (t.getTime() > now.getTime() - 12 * MINUTE) break;
      if (beat.who === "R") {
        const origin = rand.chance(0.3) ? "phone" : "agentsdr";
        const at = origin === "agentsdr" ? spaced(plan.rep, t) : t;
        plan.msgs.push({ dir: "outbound", origin, body: fillText(beat.text, person, plan.rep), at });
        prev = at;
      } else {
        plan.msgs.push({ dir: "inbound", origin: "lead", body: fillText(beat.text, person, plan.rep), at: t });
        prev = t;
      }
    }
  }

  function planCampaign(opts: {
    key: "A" | "B";
    people: DemoPerson[];
    steps: WhatsappCampaignStep[];
    /** First-send time per person, or null for a lead that is only enrolled so far. */
    starts: (Date | null)[];
    enrolled: Date[];
    cutoff: Date;
    /** How many of the leads that get messages answer. */
    replies: number;
    failedAt: number[];
    stoppedAt: number[];
    pausedCampaign: boolean;
  }) {
    const reps = rand.shuffle(opts.people.map((_, i) => REPS[i % 2]!));
    const eligible = opts.people.map((_, i) => i).filter((i) => opts.starts[i] && !opts.failedAt.includes(i) && !opts.stoppedAt.includes(i));
    // Later leads are likelier to answer: the team keeps getting better.
    const weightOf = (i: number) => {
      const start = opts.starts[i];
      const age = start ? (now.getTime() - start.getTime()) / DAY : 0;
      return age > 60 ? 0.4 : age > 40 ? 0.3 : age > 14 ? 2.4 : 1.2;
    };
    const keyed = eligible.map((i) => ({ i, key: Math.pow(rand.next(), 1 / weightOf(i)) }));
    const repliers = new Set(keyed.sort((a, b) => b.key - a.key).slice(0, opts.replies).map((k) => k.i));
    opts.people.forEach((person, i) => {
      const rep = reps[i]!;
      const start = opts.starts[i] ?? null;
      const lead: LeadPlan = {
        id: randomUUID(),
        person,
        rep,
        enrolledAt: opts.enrolled[i]!,
        status: "queued",
        currentStep: 0,
        nextSendAt: null,
        lastSentAt: null,
        repliedAt: null,
        lastError: null,
        attempts: 0,
        sends: [],
        chat: null,
      };
      leadPlans[opts.key].push(lead);
      if (!start) {
        // Enrolled, not yet sent: the next tick of the sender picks it up.
        lead.nextSendAt = atBiz(ctx, plusHours(now, rand.int(10, 20)));
        return;
      }
      const times: Date[] = [spaced(rep, start)];
      for (let s = 1; s < opts.steps.length; s++) times.push(spaced(rep, atBiz(ctx, plusHours(times[s - 1]!, opts.steps[s]!.delayHours))));

      if (opts.failedAt.includes(i)) {
        lead.status = "failed";
        lead.attempts = 3;
        lead.lastError = "This number isn't on WhatsApp";
        lead.sends.push({ id: randomUUID(), step: 0, stepId: opts.steps[0]!.id, at: times[0]!, body: renderStep(opts.steps[0]!.body, person, rand), status: "failed", error: lead.lastError });
        lead.lastSentAt = null;
        return;
      }

      if (opts.stoppedAt.includes(i)) {
        // Stopped by a person before anything went out: nobody is counted as messaged without a message.
        lead.status = "stopped";
        lead.nextSendAt = null;
        return;
      }

      // Will they answer, and after which message?
      let replyAt: Date | null = null;
      let replyAfterStep = 0;
      if (repliers.has(i)) {
        const maxStep = opts.steps.length - 1;
        replyAfterStep = Math.min(maxStep, rand.weighted([[0, 60], [1, 27], [2, 13]] as const));
        const base = times[replyAfterStep]!;
        const gapMin = rand.chance(0.45) ? rand.int(4, 90) : rand.int(100, 1700);
        let at = gapMin > 240 ? humanize(ctx, plusMin(base, gapMin)) : plusMin(base, gapMin);
        const nextStep = times[replyAfterStep + 1];
        if (nextStep && at.getTime() > nextStep.getTime() - 30 * MINUTE) at = new Date(nextStep.getTime() - rand.int(35, 300) * MINUTE);
        if (base.getTime() <= opts.cutoff.getTime() && at.getTime() > base.getTime() + MINUTE && at.getTime() < now.getTime() - 5 * MINUTE) replyAt = at;
      }
      const stopAt = opts.stoppedAt.includes(i) ? Math.min(1, opts.steps.length - 1) : null;

      const chat: ChatPlan = { person, rep, msgs: [], intent: null, unread: 0, fromCampaign: true, handled: false };
      for (let s = 0; s < opts.steps.length; s++) {
        const at = times[s]!;
        if (at.getTime() > opts.cutoff.getTime()) break;
        if (replyAt && s > replyAfterStep) break;
        if (stopAt !== null && s >= stopAt) break;
        const body = renderStep(opts.steps[s]!.body, person, rand);
        const send: SendPlan = { id: randomUUID(), step: s, stepId: opts.steps[s]!.id, at, body, status: "sent", error: null };
        lead.sends.push(send);
        chat.msgs.push({ dir: "outbound", origin: "agentsdr", body, at, sendId: send.id });
      }
      // A rep who sees a fresh message sit unanswered sometimes adds a line from their phone.
      const lastSend = lead.sends.at(-1);
      if (!replyAt && lastSend && now.getTime() - lastSend.at.getTime() < 5 * DAY && rand.chance(0.45)) {
        const at = humanize(ctx, plusMin(lastSend.at, rand.int(180, 1100)));
        if (at.getTime() < now.getTime() - 20 * MINUTE) {
          chat.msgs.push({ dir: "outbound", origin: "phone", body: fillText(rand.pick(PHONE_NUDGES), person, rep), at });
        }
      }
      lead.currentStep = lead.sends.length;
      lead.lastSentAt = lead.sends.at(-1)?.at ?? null;
      lead.chat = chat;
      chatPlans.push(chat);

      if (replyAt) {
        lead.status = "replied";
        lead.repliedAt = replyAt;
        // Out-of-office auto-replies are rare in a chat app: keep a couple.
        let intent = rand.weighted(REPLY_MIX);
        if (intent === "Out of Office" && oooSeen >= 2) intent = rand.weighted(REPLY_MIX.filter(([i]) => i !== "Out of Office"));
        if (intent === "Out of Office") oooSeen++;
        const handled = HANDLED_INTENTS.has(intent) && now.getTime() - replyAt.getTime() > 6 * DAY && rand.chance(0.25);
        appendReplyThread(chat, replyAt, intent, handled);
        chat.handled = handled && chat.msgs.at(-1)!.dir === "outbound";
      } else if (stopAt !== null && lead.sends.length) {
        lead.status = "stopped";
      } else if (lead.sends.length >= opts.steps.length) {
        lead.status = "completed";
      } else {
        lead.status = "in_sequence";
        lead.nextSendAt = times[lead.sends.length] ?? null;
      }
    });
  }

  // A: three waves, the last one still going out.
  {
    const starts: (Date | null)[] = [];
    const enrolled: Date[] = [];
    const wave = (day: number, n: number, spreadDays: number, queuedTail = 0) => {
      const e = workTime(ctx, day);
      for (let i = 0; i < n; i++) {
        enrolled.push(plusMin(e, i));
        if (i >= n - queuedTail) starts.push(null);
        else starts.push(atBiz(ctx, plusHours(daysAgo(ctx, day), Math.floor((i / Math.max(1, n - queuedTail)) * spreadDays * 24))));
      }
    };
    wave(74, 8, 2);
    wave(50, 8, 2);
    wave(24, 10, 2);
    wave(3, 10, 2.3, 3);
    // The queued ones were added this morning.
    for (let i = enrolled.length - 3; i < enrolled.length; i++) enrolled[i] = new Date(now.getTime() - rand.int(20, 150) * MINUTE);
    // Starts that landed in the future (today's later slots) wait their turn.
    for (let i = 0; i < starts.length; i++) {
      const s = starts[i];
      if (s && s.getTime() > now.getTime() - 15 * MINUTE) starts[i] = new Date(now.getTime() - rand.int(30, 600) * MINUTE);
    }
    planCampaign({
      key: "A", people: peopleA, steps: CAMPAIGN_A_STEPS, starts, enrolled, cutoff: now,
      replies: 13, failedAt: [5], stoppedAt: [16], pausedCampaign: false,
    });
  }

  // B: ran for a fortnight, paused when the webinar window closed.
  const bPausedAt = workTime(ctx, 19);
  {
    const enrolled: Date[] = [];
    const starts: (Date | null)[] = [];
    const base = workTime(ctx, 35);
    for (let i = 0; i < B_COUNT; i++) {
      enrolled.push(plusMin(base, i));
      starts.push(i >= B_COUNT - 5 ? null : atBiz(ctx, plusHours(daysAgo(ctx, 33), Math.floor((i / (B_COUNT - 5)) * 9 * 24))));
    }
    planCampaign({
      key: "B", people: peopleB, steps: CAMPAIGN_B_STEPS, starts, enrolled, cutoff: bPausedAt,
      replies: 8, failedAt: [9], stoppedAt: [14], pausedCampaign: true,
    });
  }

  // --- organic chats ------------------------------------------------------
  ORGANIC.forEach((script, i) => {
    const person = peopleOrganic[i]!;
    const plan: ChatPlan = { person, rep: script.rep, msgs: [], intent: script.intent, unread: 0, fromCampaign: false, handled: false };
    let prev = humanize(ctx, plusMin(daysAgo(ctx, script.day), rand.int(0, 90)));
    if (prev.getTime() > now.getTime() - 30 * MINUTE) prev = new Date(now.getTime() - rand.int(40, 400) * MINUTE);
    script.beats.forEach((beat, bi) => {
      const t = bi === 0 ? prev : humanize(ctx, plusMin(prev, rand.int(beat.gap[0], beat.gap[1])));
      if (t.getTime() > now.getTime() - 8 * MINUTE) return;
      if (beat.who === "R") {
        const origin = rand.chance(script.phoneRep) ? "phone" : "agentsdr";
        const at = origin === "agentsdr" ? spaced(plan.rep, t) : t;
        plan.msgs.push({ dir: "outbound", origin, body: fillText(beat.text, person, plan.rep), at });
        prev = at;
      } else {
        plan.msgs.push({ dir: "inbound", origin: "lead", body: fillText(beat.text, person, plan.rep), at: t });
        prev = t;
      }
    });
    plan.handled = plan.intent !== null && plan.msgs.some((m) => m.dir === "inbound") && plan.msgs.at(-1)?.dir === "outbound";
    chatPlans.push(plan);
  });

  // =========================================================================
  // Calls (planned before anything is written: a follow-up message opened
  // after a call becomes a message in that lead's chat)
  // =========================================================================

  // Leads whose worked thread is over: only they are called, and only after it ended.
  const threadEnd = new Map<string, { end: Date; intent: ReplyIntent }>();
  for (const plan of chatPlans) {
    if (!plan.intent || !plan.handled) continue;
    if (!["Meeting Requested", "Demo Request", "Information Requested", "Trial Requested", "Case Study"].includes(plan.intent)) continue;
    const end = plan.msgs.at(-1)!.at;
    if (now.getTime() - end.getTime() > 3 * DAY) threadEnd.set(plan.person.id, { end, intent: plan.intent });
  }
  const chatPeople = rand.shuffle(ctx.pools.whatsapp.filter((p) => threadEnd.has(p.id)));
  const callOnlyPeople = rand.shuffle([...peopleRest]);

  const C_COUNT = 30;
  const D_COUNT = 20;
  // People asking about a trial or the product belong to the expansion list; the rest asked for a call.
  const dFromChats = chatPeople.filter((p) => ["Trial Requested", "Information Requested"].includes(threadEnd.get(p.id)!.intent)).slice(0, 1);
  const cFromChats = chatPeople.filter((p) => !dFromChats.includes(p)).slice(0, 4);
  const cPeople = [...cFromChats, ...callOnlyPeople.slice(0, C_COUNT - cFromChats.length)];
  const dPeople = [...dFromChats, ...callOnlyPeople.slice(C_COUNT - cFromChats.length, C_COUNT - cFromChats.length + D_COUNT - dFromChats.length)];

  const chatByPerson = new Map(chatPlans.map((c) => [c.person.id, c]));
  const callPlan = planCalls();

  // Follow-up messages become chat messages (a new chat when the lead has none).
  for (const msg of callPlan.messages) {
    let chat = chatByPerson.get(msg.person.id);
    if (!chat) {
      chat = { person: msg.person, rep: rand.pick(REPS), msgs: [], intent: null, unread: 0, fromCampaign: false, handled: false };
      chatByPerson.set(msg.person.id, chat);
      chatPlans.push(chat);
    }
    chat.msgs.push({ dir: "outbound", origin: "phone", body: msg.body, at: plusMin(msg.openedAt, 0.4 + rand.next() * 0.8), callSessionId: msg.callSessionId });
  }

  // Order, then unread: the freshest unanswered replies.
  for (const chat of chatPlans) chat.msgs.sort((a, b) => a.at.getTime() - b.at.getTime());
  const trailing = (chat: ChatPlan) => {
    let n = 0;
    for (let i = chat.msgs.length - 1; i >= 0 && chat.msgs[i]!.dir === "inbound"; i--) n++;
    return n;
  };
  const waiting = chatPlans
    .filter((c) => trailing(c) > 0 && now.getTime() - c.msgs.at(-1)!.at.getTime() < 5 * DAY)
    .sort((a, b) => b.msgs.at(-1)!.at.getTime() - a.msgs.at(-1)!.at.getTime());
  for (const chat of waiting.slice(0, 6)) chat.unread = Math.min(3, trailing(chat));

  // =========================================================================
  // Write: accounts, campaigns
  // =========================================================================

  const accountIds = {} as Record<Rep, { id: string; unipileId: string }>;
  for (const rep of REPS) {
    const [row] = await db
      .insert(whatsappAccounts)
      .values({
        organizationId: org,
        unipileAccountId: `demo-wa-${rep}`,
        name: TEAM[rep].name,
        phone: TEAM[rep].phone,
        status: "connected",
        connectedAt: daysAgo(ctx, rep === "jordan" ? 84 : 79),
        isDefault: rep === "jordan",
        newChatsPerDay: null,
        lastSyncedAt: new Date(now.getTime() - rand.int(20, 200) * MINUTE),
        createdAt: daysAgo(ctx, rep === "jordan" ? 84 : 79),
        updatedAt: now,
      })
      .returning({ id: whatsappAccounts.id });
    accountIds[rep] = { id: row!.id, unipileId: `demo-wa-${rep}` };
  }
  count(ctx, "whatsapp numbers", 2);

  const [campA] = await db
    .insert(whatsappCampaigns)
    .values({
      organizationId: org,
      name: "Sales leaders · Signal intro",
      description: "Three short messages to heads of sales and RevOps: the pitch in one line, a nudge, and a polite goodbye.",
      status: "active",
      steps: CAMPAIGN_A_STEPS,
      createdAt: daysAgo(ctx, 76),
      updatedAt: daysAgo(ctx, 3),
    })
    .returning({ id: whatsappCampaigns.id });
  const [campB] = await db
    .insert(whatsappCampaigns)
    .values({
      organizationId: org,
      name: "Webinar no-shows · Sept",
      description: "People who registered for the September webinar and did not join. Send the replay, ask once more.",
      status: "paused",
      steps: CAMPAIGN_B_STEPS,
      createdAt: daysAgo(ctx, 36),
      updatedAt: bPausedAt,
    })
    .returning({ id: whatsappCampaigns.id });
  await db.insert(whatsappCampaignAccounts).values([
    { campaignId: campA!.id, accountId: accountIds.jordan.id, createdAt: daysAgo(ctx, 76) },
    { campaignId: campA!.id, accountId: accountIds.lena.id, createdAt: daysAgo(ctx, 76) },
    { campaignId: campB!.id, accountId: accountIds.jordan.id, createdAt: daysAgo(ctx, 36) },
    { campaignId: campB!.id, accountId: accountIds.lena.id, createdAt: daysAgo(ctx, 36) },
  ]);

  const leadRows = (campaignId: string, leads: LeadPlan[]) =>
    leads.map((lead) => ({
      id: lead.id,
      campaignId,
      personId: lead.person.id,
      phone: lead.person.phone!,
      customFields: {} as Record<string, string>,
      status: lead.status,
      currentStep: lead.currentStep,
      nextSendAt: lead.nextSendAt,
      accountId: lead.sends.length ? accountIds[lead.rep].id : null,
      attempts: lead.attempts,
      lastError: lead.lastError,
      lastSentAt: lead.lastSentAt,
      repliedAt: lead.repliedAt,
      createdAt: lead.enrolledAt,
      updatedAt: lead.repliedAt ?? lead.lastSentAt ?? lead.enrolledAt,
    }));
  await db.insert(whatsappCampaignLeads).values(leadRows(campA!.id, leadPlans.A));
  await db.insert(whatsappCampaignLeads).values(leadRows(campB!.id, leadPlans.B));
  count(ctx, "whatsapp message campaigns", 2);
  count(ctx, "whatsapp campaign leads", leadPlans.A.length + leadPlans.B.length);

  // =========================================================================
  // Write: call campaigns, contacts, sessions (messages reference sessions)
  // =========================================================================
  await persistCalls(callPlan);

  // =========================================================================
  // Write: chats and messages (replies go through the CRM bridge)
  // =========================================================================
  const subRows = await db
    .select({ id: crmSubcategories.id, name: crmSubcategories.name, categoryKey: crmSubcategories.categoryKey })
    .from(crmSubcategories)
    .where(eq(crmSubcategories.pipelineId, ctx.pipelineId));
  const subIdByName = new Map(subRows.map((r) => [r.name, r]));
  let handledCount = 0;

  /** The database clock, to tell which rows a call just wrote. */
  async function clockMarker(): Promise<string> {
    const [row] = await db.execute<{ t: string }>(sql`select clock_timestamp()::text as t`);
    return row!.t;
  }
  /** crm_events are append-only; the seed puts what a step just wrote at the time it happened. */
  async function restampEvents(personId: string, marker: string, at: Date): Promise<void> {
    await db.transaction(async (tx) => {
      await tx.execute(sql`set local session_replication_role = replica`);
      await tx.execute(sql`
        with v as (
          select id, row_number() over (order by created_at, id) as rn from crm_events
           where organization_id = ${org} and person_id = ${personId}::uuid and created_at > ${marker}::timestamptz)
        update crm_events e set created_at = ${at.toISOString()}::timestamptz + (v.rn - 1) * interval '1 second'
          from v where e.id = v.id`);
    });
  }

  let wamid = 0;
  const messageIdBySend = new Map<string, string>();
  const crmThreads: { chat: ChatPlan; chatId: string; lastInboundCrmId: string | null }[] = [];

  const ordered = [...chatPlans].sort((a, b) => a.msgs[0]!.at.getTime() - b.msgs[0]!.at.getTime());
  for (const [index, chat] of ordered.entries()) {
    const first = chat.msgs[0]!;
    const last = chat.msgs.at(-1)!;
    const account = accountIds[chat.rep];
    const phone = chat.person.phone!;
    const unipileChatId = `demo-chat-${String(index + 1).padStart(3, "0")}`;
    const [chatRow] = await db
      .insert(whatsappChats)
      .values({
        accountId: account.id,
        unipileChatId,
        providerId: `${digitsOf(phone)}@s.whatsapp.net`,
        phone,
        personId: chat.person.id,
        name: chat.person.fullName,
        lastMessageAt: last.at,
        lastMessagePreview: preview(last.body),
        lastDirection: last.dir,
        unreadCount: chat.unread,
        createdAt: first.at,
        updatedAt: last.at,
      })
      .returning({ id: whatsappChats.id });
    const chatId = chatRow!.id;

    const hasInbound = chat.msgs.some((m) => m.dir === "inbound");
    const rowFor = (m: PlannedMsg, i: number) => {
      const laterInbound = chat.msgs.slice(i + 1).find((x) => x.dir === "inbound");
      let readAt: Date | null = null;
      if (m.dir === "outbound") {
        if (laterInbound) readAt = new Date(Math.max(m.at.getTime() + 20_000, laterInbound.at.getTime() - rand.int(20, 600) * 1000));
        else if (rand.chance(0.75)) {
          const t = plusMin(m.at, rand.int(2, 900));
          if (t.getTime() < now.getTime() - MINUTE) readAt = t;
        }
      }
      return {
        chatId,
        unipileMessageId: `demo-wamid-${(++wamid).toString().padStart(5, "0")}`,
        direction: m.dir,
        origin: m.origin,
        body: m.body,
        attachments: [],
        sentAt: m.at,
        deliveredAt: m.dir === "outbound" ? new Date(m.at.getTime() + rand.int(1, 12) * 1000) : null,
        readAt,
        callSessionId: m.callSessionId ?? null,
        raw: m.origin === "agentsdr" ? null : { source: "demo-seed" },
        createdAt: m.at,
      };
    };

    if (!hasInbound) {
      const rows = chat.msgs.map(rowFor);
      const inserted = await db.insert(whatsappMessages).values(rows).returning({ id: whatsappMessages.id, unipileMessageId: whatsappMessages.unipileMessageId });
      const byWamid = new Map(inserted.map((r) => [r.unipileMessageId, r.id]));
      chat.msgs.forEach((m, i) => {
        if (m.sendId) messageIdBySend.set(m.sendId, byWamid.get(rows[i]!.unipileMessageId)!);
      });
      continue;
    }

    // A chat the lead is in: one message at a time, so the CRM sees the thread
    // in order (it backfills what the rep sent before the first reply). Every
    // step is stamped at the message's own time.
    let crmActive = false;
    let lastInboundCrmId: string | null = null;
    let recordId: string | null = null;
    for (const [i, m] of chat.msgs.entries()) {
      const row = rowFor(m, i);
      const [stored] = await db.insert(whatsappMessages).values(row).returning({ id: whatsappMessages.id });
      const messageId = stored!.id;
      if (m.sendId) messageIdBySend.set(m.sendId, messageId);
      const input = {
        personId: chat.person.id,
        unipileAccountId: account.unipileId,
        unipileChatId,
        providerContactId: `${digitsOf(phone)}@s.whatsapp.net`,
        unipileMessageId: row.unipileMessageId,
        body: m.body,
        sentAt: m.at,
        raw: { source: "demo-seed" },
      };
      let crmId: string | null = null;
      const marker = await clockMarker();
      if (m.dir === "inbound") {
        crmId = (await forwardWhatsappInboundToCrm(input)).crmConversationMessageId;
        if (crmId) {
          crmActive = true;
          lastInboundCrmId = crmId;
        }
      } else if (crmActive) {
        crmId = (await recordWhatsappOutboundInCrm({ ...input, origin: m.origin as "agentsdr" | "phone" })).crmConversationMessageId;
      }
      if (crmId) {
        await db.update(whatsappMessages).set({ crmConversationMessageId: crmId }).where(eq(whatsappMessages.id, messageId));
        await restampEvents(chat.person.id, marker, m.at);
      }
    }
    if (chat.handled && lastInboundCrmId) {
      const [found] = await db.execute<{ crm_record_id: string }>(sql`
        select c.crm_record_id from crm_conversation_messages m join crm_conversations c on c.id = m.conversation_id where m.id = ${lastInboundCrmId}`);
      recordId = found?.crm_record_id ?? null;
      const sub = chat.intent ? subIdByName.get(chat.intent) : null;
      if (recordId && sub) {
        const marker = await clockMarker();
        const actor = ctx.users[chat.rep].id;
        await withCrmTransaction(async (tx) => {
          const record = await lockCrmRecord(tx, recordId!);
          await setRecordClassificationInTransaction(tx, {
            recordId: recordId!,
            categoryKey: sub.categoryKey as CrmCategoryKey,
            subcategoryId: sub.id,
            source: "human",
            actorType: "human",
            actorRef: actor,
            expectedContextVersion: record.contextVersion,
            reason: "Sorted from the WhatsApp thread",
          });
          await transitionWorkflowInTransaction(tx, { recordId: recordId!, to: "idle", actorType: "human", actorRef: actor, reason: "Answered on WhatsApp" });
        });
        await restampEvents(chat.person.id, marker, plusMin(chat.msgs.at(-1)!.at, rand.int(3, 25)));
        handledCount++;
      }
    }
    crmThreads.push({ chat, chatId, lastInboundCrmId });
  }

  // Replies for crm.ts: the last thing each lead said, as the CRM holds it.
  const mix: Record<string, number> = {};
  for (const thread of crmThreads) {
    if (!thread.lastInboundCrmId || !thread.chat.intent || thread.chat.handled) continue;
    const [row] = await db.execute<{ conversation_id: string; crm_record_id: string; sent_at: Date | string }>(sql`
      select m.conversation_id, c.crm_record_id, m.sent_at
        from crm_conversation_messages m
        join crm_conversations c on c.id = m.conversation_id
       where m.id = ${thread.lastInboundCrmId}`);
    if (!row) continue;
    ctx.replies.push({
      recordId: row.crm_record_id,
      personId: thread.chat.person.id,
      conversationId: row.conversation_id,
      messageId: thread.lastInboundCrmId,
      channel: "whatsapp",
      intent: thread.chat.intent,
      sentAt: new Date(row.sent_at),
      rep: thread.chat.rep,
    });
    mix[thread.chat.intent] = (mix[thread.chat.intent] ?? 0) + 1;
  }

  // Campaign sends, now that their messages exist.
  const sendRows: (typeof whatsappCampaignSends.$inferInsert)[] = [];
  for (const lead of [...leadPlans.A, ...leadPlans.B]) {
    for (const send of lead.sends) {
      sendRows.push({
        leadId: lead.id,
        step: send.step,
        stepId: send.stepId,
        status: send.status,
        accountId: accountIds[lead.rep].id,
        whatsappMessageId: send.status === "sent" ? messageIdBySend.get(send.id) ?? null : null,
        body: send.body,
        error: send.error,
        createdAt: send.at,
        sentAt: send.status === "sent" ? send.at : null,
      });
    }
  }
  await insertInBatches(sendRows, 200, (batch) => db.insert(whatsappCampaignSends).values(batch));

  // Chats' "updated" stamps follow their last message (the helpers above stamp now).
  await db.execute(sql`
    update whatsapp_chats c set updated_at = coalesce(c.last_message_at, c.created_at)
      from whatsapp_accounts a where a.id = c.account_id and a.organization_id = ${org}`);

  // The delivery ledger entries the bridge wrote carry the message's own time.
  await db.execute(sql`
    update crm_webhook_events e set created_at = m.sent_at + interval '2 seconds'
      from whatsapp_messages m
     where e.organization_id = ${org} and e.source = 'whatsapp'
       and e.payload->>'unipileMessageId' = m.unipile_message_id`);

  count(ctx, "whatsapp threads classified by hand", handledCount);
  count(ctx, "whatsapp chats", chatPlans.length);
  count(ctx, "whatsapp messages", chatPlans.reduce((n, c) => n + c.msgs.length, 0));
  count(ctx, "whatsapp campaign sends", sendRows.length);
  count(ctx, "whatsapp replies to the CRM", Object.values(mix).reduce((a, b) => a + b, 0));
  count(ctx, "whatsapp unread chats", chatPlans.filter((c) => c.unread > 0).length);
  console.log(`\n    whatsapp reply intents: ${JSON.stringify(mix)}`);

  // =========================================================================
  // Calls: the plan
  // =========================================================================

  type CallOutcomeKind = "connected" | "no_answer" | "busy" | "failed" | "not_on_whatsapp" | "wrong_number";

  type PlannedCall = {
    id: string;
    at: Date;
    kind: CallOutcomeKind;
    scenario: Scenario | null;
    startedAt: Date | null;
    endedAt: Date | null;
    talkMs: number | null;
    offsetMs: number | null;
    error: string | null;
    transcript: CallTranscript | null;
    contactCall: ContactCallStatus;
  };

  type ContactPlan = {
    id: string;
    campaign: "C" | "D";
    person: DemoPerson;
    createdAt: Date;
    calls: PlannedCall[];
    state: ContactCallState;
    notes: string | null;
    lastScenario: Scenario | null;
    holdUncalled: boolean;
    stageForCrm: { category: "interested" | "customer" | "not_interested" | "other"; sub: string } | null;
  };

  type CallPlan = {
    campaigns: { key: "C" | "D"; id: string; name: string; description: string; status: "active" | "paused"; createdAt: Date }[];
    contacts: ContactPlan[];
    messages: { person: DemoPerson; contact: ContactPlan; callSessionId: string; body: string; openedAt: Date }[];
  };

  function planCalls(): CallPlan {
    const campaigns: CallPlan["campaigns"] = [
      {
        key: "C", id: randomUUID(), name: "Inbound demo requests · call within the hour",
        description: "Everyone who fills in the demo form gets a call from a rep inside the hour.",
        status: "active", createdAt: daysAgo(ctx, 75),
      },
      {
        key: "D", id: randomUUID(), name: "Existing trials · move to Team",
        description: "Trial accounts with three or more active users: talk about moving to the Team plan before the pilot ends.",
        status: "active", createdAt: daysAgo(ctx, 44),
      },
    ];
    const contacts: ContactPlan[] = [];
    const messages: CallPlan["messages"] = [];
    const used = new Map<string, number>();

    const makeContact = (campaign: "C" | "D", person: DemoPerson, createdAt: Date, hold = false): ContactPlan => ({
      id: randomUUID(), campaign, person, createdAt, calls: [],
      state: { callStatus: "new", stage: "to_call", unansweredAttempts: 0, followUpAt: null },
      notes: null, lastScenario: null, holdUncalled: hold, stageForCrm: null,
    });

    // C: leads drift in all through the last two months, more of them lately.
    cPeople.forEach((person, i) => {
      const chatReply = threadEnd.get(person.id)?.end;
      let created: Date;
      if (chatReply) created = atBiz(ctx, plusMin(chatReply, rand.int(20 * 60, 9 * 24 * 60)));
      else created = workTime(ctx, i % 5 === 2 ? rand.int(1, 5) : Math.floor(72 * Math.pow(rand.next(), 1.35)));
      let hold = false;
      if (!chatReply && i >= cPeople.length - 5) {
        created = new Date(now.getTime() - rand.int(4, 55) * MINUTE);
        hold = true;
      }
      if (created.getTime() > now.getTime() - 3 * MINUTE) created = new Date(now.getTime() - rand.int(5, 60) * MINUTE);
      contacts.push(makeContact("C", person, created, hold));
    });
    // D: two imports of trial accounts (six weeks and three weeks ago), then a few added one by one.
    const importA = workTime(ctx, 42);
    const importB = workTime(ctx, 23);
    const firstCallAfterHours = new Map<string, number>();
    dPeople.forEach((person, i) => {
      const chatReply = threadEnd.get(person.id)?.end;
      let created: Date;
      let after = rand.int(3, 30);
      if (i < 8) {
        created = plusMin(importA, i % 4);
        after = 24 * (1 + Math.floor(i / 2.6)) + rand.int(0, 5);
      } else if (i < dPeople.length - 6) {
        created = plusMin(importB, i % 4);
        after = 24 * (1 + Math.floor((i - 8) / 2.4)) + rand.int(0, 5);
      } else created = workTime(ctx, rand.int(1, 14));
      if (chatReply && created.getTime() < chatReply.getTime() + 20 * HOUR) {
        created = atBiz(ctx, plusMin(chatReply, rand.int(20 * 60, 7 * 24 * 60)));
        after = rand.int(3, 30);
      }
      const hold = i >= dPeople.length - 2;
      if (hold) created = new Date(now.getTime() - rand.int(30, 280) * MINUTE);
      const contact = makeContact("D", person, created, hold);
      firstCallAfterHours.set(contact.id, after);
      contacts.push(contact);
    });

    const pickScenario = (campaign: "C" | "D", followUp: boolean, not: string | null, positiveOnly: boolean): Scenario => {
      // A lead who is already in the CRM as interested is not later written off on a call.
      const pool = SCENARIOS.filter((s) => (campaign === "C" ? s.c : s.d) > 0 && (!followUp || !s.endsCall) && s.key !== not && (!positiveOnly || s.category === "interested" || s.category === "customer"));
      const weights = pool.map((s) => [s, (campaign === "C" ? s.c : s.d) / (1 + 0.8 * (used.get(s.key) ?? 0))] as const);
      const scenario = rand.weighted(weights);
      used.set(scenario.key, (used.get(scenario.key) ?? 0) + 1);
      return scenario;
    };

    // The rep who works a lead is the same one on every call.
    const callers = new Map<string, Rep>();
    const callerOf = (c: ContactPlan): Rep => {
      let rep = callers.get(c.id);
      if (!rep) callers.set(c.id, (rep = chatByPerson.get(c.person.id)?.rep ?? rand.pick(REPS)));
      return rep;
    };
    for (const contact of contacts) {
      if (contact.holdUncalled) continue;
      const chat = chatByPerson.get(contact.person.id);
      let t: Date;
      if (contact.campaign === "C") t = plusMin(contact.createdAt, rand.int(6, 80));
      else t = atBiz(ctx, plusHours(contact.createdAt, firstCallAfterHours.get(contact.id) ?? 24));
      let state = contact.state;
      let connected = 0;

      for (let n = 0; n < 4; n++) {
        if (t.getTime() > now.getTime() - 25 * MINUTE) break;
        const followUpCall = connected > 0;
        // Someone who has already talked to us is not chased forever.
        if (followUpCall && state.unansweredAttempts >= 2) break;
        let kind: CallOutcomeKind = followUpCall
          ? rand.weighted([["connected", 72], ["no_answer", 22], ["busy", 6]] as const)
          : n === 0
            ? rand.weighted([["connected", 42], ["no_answer", 36], ["busy", 10], ["failed", 5], ["not_on_whatsapp", 2], ["wrong_number", 2]] as const)
            : rand.weighted([["connected", 32], ["no_answer", 52], ["busy", 12], ["failed", 4]] as const);
        // A lead who wrote to us on WhatsApp is on WhatsApp, and is who we think.
        if (chat && (kind === "not_on_whatsapp" || kind === "wrong_number")) kind = "no_answer";
        const callId = randomUUID();
        const call: PlannedCall = {
          id: callId, at: t, kind, scenario: null, startedAt: null, endedAt: null, talkMs: null, offsetMs: null,
          error: null, transcript: null, contactCall: "no_answer",
        };

        if (kind === "connected" || kind === "wrong_number") {
          const scenario = kind === "wrong_number" ? WRONG_NUMBER : pickScenario(contact.campaign, followUpCall, contact.lastScenario?.key ?? null, Boolean(chat));
          const vars = { lead: contact.person.firstName, rep: TEAM[callerOf(contact)].first, company: contact.person.company.name, industry: contact.person.company.industry };
          const offsetSec = rand.int(4, 16);
          const timed = timeUtterances(scenario.lines.map(([who, text]) => [who, fillCall(text, vars)] as const), offsetSec);
          const pickUp = plusMin(t, 0.25 + rand.next() * 0.4);
          call.scenario = scenario;
          call.offsetMs = offsetSec * 1000;
          call.talkMs = Math.round((timed.talkSeconds + rand.int(2, 9)) * 1000);
          call.startedAt = pickUp;
          call.endedAt = new Date(pickUp.getTime() + call.talkMs);
          call.transcript = { language: "en", summary: fillCall(scenario.summary, vars), utterances: timed.utterances, model: "google/gemini-2.5-flash" };
          call.contactCall = "connected";
          connected++;
          state = nextContactCallState(state, "connected", call.endedAt);
          if (kind === "wrong_number") {
            state = { ...state, callStatus: "wrong_number", stage: "done", followUpAt: null };
            call.contactCall = "wrong_number";
          } else if (scenario.done) {
            state = { ...state, stage: "done", followUpAt: null };
          } else {
            const days = rand.int(scenario.follow.min, scenario.follow.max);
            state = { ...state, stage: "follow_up", followUpAt: atBiz(ctx, plusHours(call.endedAt, days * 24)) };
          }
          contact.lastScenario = scenario;
          contact.notes = scenario.note && rand.chance(0.75) ? fillCall(scenario.note, vars) : contact.notes;
          contact.stageForCrm = kind === "wrong_number" ? null : { category: scenario.category, sub: scenario.sub };
          // A follow-up message opened right after the call.
          const msgChance = chat ? 0.7 : 0.12;
          if (scenario.msg && rand.chance(msgChance) && kind !== "wrong_number") {
            const openedAt = plusMin(call.endedAt, rand.int(1, 18));
            const body = fillCall(scenario.msg, { ...vars, first: contact.person.firstName });
            if (!messages.some((m) => m.contact === contact && m.body === body)) messages.push({ person: contact.person, contact, callSessionId: callId, body, openedAt });
          }
          contact.calls.push(call);

          if (kind === "wrong_number" || scenario.done) break;
          const due = state.followUpAt!;
          if (due.getTime() < now.getTime() - 3 * HOUR && connected < 3 && rand.chance(0.5)) {
            t = new Date(Math.max(due.getTime() - 4 * HOUR, call.endedAt.getTime() + 20 * HOUR));
            t = atBiz(ctx, t);
            if (t.getTime() > due.getTime() + 20 * HOUR) t = due;
            continue;
          }
          break;
        }

        // Not a conversation.
        const ring = rand.int(22, 48);
        call.startedAt = t;
        call.endedAt = new Date(t.getTime() + ring * 1000);
        if (kind === "failed") {
          call.error = "The call could not be placed: WhatsApp Web was not ready";
          call.contactCall = "failed";
        } else if (kind === "not_on_whatsapp") {
          call.error = "This number isn't on WhatsApp";
          call.contactCall = "not_on_whatsapp";
        } else {
          call.contactCall = kind === "busy" ? "busy" : "no_answer";
        }
        const next = nextContactCallState(state, kind === "busy" ? "busy" : kind === "failed" ? "failed" : kind === "not_on_whatsapp" ? "not_on_whatsapp" : "no_answer", call.endedAt);
        state = next;
        // A WhatsApp message after a call nobody picked up.
        if ((kind === "no_answer" || kind === "busy") && chat && rand.chance(0.55)) {
          const body = kind === "busy"
            ? `Hi ${contact.person.firstName}, sorry to catch you at a busy moment. When would suit you for a quick call?`
            : `Hi ${contact.person.firstName}, I just tried calling you. Is there a good time for a quick 2-minute call?`;
          messages.push({ person: contact.person, contact, callSessionId: call.id, body, openedAt: plusMin(call.endedAt, rand.int(1, 9)) });
          if (state.stage !== "done") state = { ...state, stage: "follow_up" };
        }
        contact.calls.push(call);
        if (kind === "not_on_whatsapp") break;
        if (kind === "failed") {
          if (rand.chance(0.8)) { t = atBiz(ctx, plusHours(call.endedAt, 22)); continue; }
          break;
        }
        if (state.stage === "done") break;
        const due = state.followUpAt;
        if (!due) break;
        const nextAt = atBiz(ctx, new Date(due.getTime() - rand.int(0, 6) * HOUR));
        if (nextAt.getTime() > now.getTime() - 25 * MINUTE) break;
        // Retries are worked on schedule; only the freshest may still be waiting.
        if (nextAt.getTime() > now.getTime() - 3 * DAY && !rand.chance(0.85)) break;
        t = nextAt;
      }
      // A conversation that ran its course with nothing booked is closed by the rep, not left overdue for weeks.
      if (state.followUpAt && state.stage !== "done") {
        const age = now.getTime() - state.followUpAt.getTime();
        if (age > 6 * DAY || (age > 2 * DAY && rand.chance(0.45))) state = { ...state, stage: "done", followUpAt: null };
      }
      // A lead's CRM stage follows what happened last: someone who stopped picking up has not told us they are interested.
      if (state.callStatus !== "connected") contact.stageForCrm = null;
      contact.state = state;
    }

    // A few follow-ups land today, so the Due tab has real work in it.
    const todayCandidates = contacts.filter((c) => c.state.stage === "follow_up" && c.state.followUpAt && c.state.followUpAt.getTime() > now.getTime());
    for (const c of rand.shuffle(todayCandidates).slice(0, 2)) c.state = { ...c.state, followUpAt: new Date(now.getTime() - rand.int(40, 300) * MINUTE) };

    return { campaigns, contacts, messages };
  }

  // =========================================================================
  // Calls: the write
  // =========================================================================

  async function persistCalls(plan: CallPlan) {
    await db.insert(callCampaigns).values(
      plan.campaigns.map((c) => ({
        organizationId: org, id: c.id, name: c.name, description: c.description, status: c.status,
        createdAt: c.createdAt, updatedAt: c.key === "C" ? daysAgo(ctx, 2) : daysAgo(ctx, 1),
      })),
    );
    const campaignId = (key: "C" | "D") => plan.campaigns.find((c) => c.key === key)!.id;

    await db.insert(callCampaignContacts).values(
      plan.contacts.map((c) => {
        const last = c.calls.at(-1);
        return {
          id: c.id,
          campaignId: campaignId(c.campaign),
          personId: c.person.id,
          stage: c.state.stage as CampaignContactStage,
          callStatus: c.state.callStatus,
          statusUpdatedAt: last?.endedAt ?? null,
          unansweredAttempts: c.state.unansweredAttempts,
          followUpAt: c.state.followUpAt,
          notes: c.notes,
          callCount: c.calls.length,
          lastCalledAt: last?.at ?? null,
          createdAt: c.createdAt,
          updatedAt: last?.endedAt ?? c.createdAt,
        };
      }),
    );

    const sessionRows: (typeof callSessions.$inferInsert)[] = [];
    for (const c of plan.contacts) {
      for (const call of c.calls) {
        const connected = call.contactCall === "connected" || call.contactCall === "wrong_number";
        const talkMs = call.talkMs ?? 0;
        sessionRows.push({
          organizationId: org,
          id: call.id,
          personId: c.person.id,
          campaignContactId: c.id,
          phone: c.person.phone!,
          status: connected ? "recorded" : call.kind === "failed" || call.kind === "not_on_whatsapp" ? "failed" : "no_recording",
          uploadTokenHash: sha256(randomBytes(16).toString("hex")),
          tokenExpiresAt: new Date(call.at.getTime() + 2 * HOUR),
          startedAt: call.startedAt,
          endedAt: call.endedAt,
          durationMs: connected ? talkMs : null,
          recordingKey: connected ? `demo/recordings/${call.id}.webm` : null,
          recordingBytes: connected ? Math.round(((talkMs + (call.offsetMs ?? 0)) / 1000) * 16_000) : null,
          recordingContentType: connected ? "audio/webm" : null,
          recordingOffsetMs: connected ? call.offsetMs : null,
          error: call.error,
          transcriptStatus: connected ? "done" : "none",
          transcript: call.transcript,
          transcribedAt: connected && call.endedAt ? plusMin(call.endedAt, 1 + rand.next() * 1.5) : null,
          createdAt: call.at,
          updatedAt: call.endedAt ?? call.at,
        });
      }
    }
    await insertInBatches(sessionRows, 100, (batch) => db.insert(callSessions).values(batch));

    const messageRows = plan.messages.map((m) => ({
      organizationId: org,
      personId: m.person.id,
      campaignContactId: m.contact.id,
      callSessionId: m.callSessionId,
      phone: m.person.phone!,
      body: m.body,
      openedAt: m.openedAt,
    }));
    if (messageRows.length) await db.insert(callMessages).values(messageRows);

    const connectedCalls = sessionRows.filter((r) => r.status === "recorded").length;
    count(ctx, "call campaigns", plan.campaigns.length);
    count(ctx, "call campaign contacts", plan.contacts.length);
    count(ctx, "calls", sessionRows.length);
    count(ctx, "calls connected (recorded, transcribed)", connectedCalls);
    count(ctx, "call follow-up messages", messageRows.length);

    // CRM stages for the leads who were reached and have not replied in chat
    // (those already have a record the CRM module classifies).
    const subs = await db
      .select({ id: crmSubcategories.id, name: crmSubcategories.name })
      .from(crmSubcategories)
      .where(eq(crmSubcategories.pipelineId, ctx.pipelineId));
    const subId = new Map(subs.map((s) => [s.name, s.id]));
    const replied = new Set(ctx.replies.map((r) => r.personId));
    let staged = 0;
    // The chat threads are written after this function; their records do not exist yet, so look at the plan.
    const willHaveRecord = (personId: string) => chatPlans.some((chat) => chat.person.id === personId && chat.msgs.some((m) => m.dir === "inbound"));
    for (const c of plan.contacts) {
      if (!c.stageForCrm || willHaveRecord(c.person.id) || replied.has(c.person.id)) continue;
      const id = subId.get(c.stageForCrm.sub);
      if (!id) continue;
      try {
        await setLeadStage(c.id, { categoryKey: c.stageForCrm.category, subcategoryId: id });
        staged++;
      } catch (error) {
        console.error(`    could not set the stage for call contact ${c.person.fullName}:`, error instanceof Error ? error.message : error);
      }
    }
    count(ctx, "call leads with a CRM stage", staged);
    stagedCallPeople = plan.contacts.filter((c) => c.stageForCrm && !willHaveRecord(c.person.id)).map((c) => c.person.id);
  }

  // After the threads exist: tie every session to its lead's CRM record, and
  // give records created by calls the history of those calls.
  await db.execute(sql`
    update call_sessions s set crm_record_id = r.id
      from crm_records r
     where s.organization_id = ${org} and r.organization_id = ${org}
       and r.person_id = s.person_id and s.crm_record_id is null`);
  if (stagedCallPeople.length) {
    await db.execute(sql`
      update crm_records r
         set created_at = h.first_at, updated_at = h.last_at, last_interaction_at = h.last_at
        from (select person_id, min(created_at) as first_at, max(coalesce(ended_at, created_at)) as last_at
                from call_sessions where organization_id = ${org} group by person_id) h
       where r.organization_id = ${org} and r.person_id = h.person_id
         and r.person_id in (${sql.join(stagedCallPeople.map((id) => sql`${id}::uuid`), sql`, `)})`);
  }

}

let stagedCallPeople: string[] = [];

// ---------------------------------------------------------------------------
// Call scenarios: transcripts. {lead} {rep} {company} {industry}; {first} in messages.
// ---------------------------------------------------------------------------

type Spk = "rep" | "lead";
type Scenario = {
  key: string;
  /** Weights in the inbound-demo campaign (c) and the expansion campaign (d). */
  c: number;
  d: number;
  /** The call ends the conversation: no follow-up date, nothing to chase. */
  done?: boolean;
  /** Not a candidate for a follow-up call (a refusal, a wrong person). */
  endsCall?: boolean;
  follow: { min: number; max: number };
  category: "interested" | "customer" | "not_interested" | "other";
  sub: string;
  summary: string;
  note?: string;
  /** What the rep opened in WhatsApp afterwards. */
  msg?: string;
  lines: (readonly [Spk, string])[];
};

function fillCall(text: string, v: { lead: string; rep: string; company: string; industry: string; first?: string }): string {
  return text
    .replaceAll("{lead}", v.lead)
    .replaceAll("{rep}", v.rep)
    .replaceAll("{company}", v.company)
    .replaceAll("{industry}", v.industry)
    .replaceAll("{first}", v.first ?? v.lead);
}

/** Start times for each line from how long it takes to say, with a pause between. */
function timeUtterances(lines: (readonly [Spk, string])[], offsetSeconds: number) {
  let t = offsetSeconds + 1;
  const utterances: CallTranscript["utterances"] = [];
  for (const [speaker, text] of lines) {
    utterances.push({ startSeconds: Math.round(t), speaker, text });
    const words = text.split(/\s+/).length;
    t += words / 1.15 + 2.2 + (words % 4) + (words % 7 === 0 ? 5 : 0);
  }
  return { utterances, talkSeconds: t - offsetSeconds };
}

const rep = (text: string) => ["rep", text] as const;
const lead = (text: string) => ["lead", text] as const;

const SCENARIOS: Scenario[] = [
  {
    key: "discovery",
    c: 10, d: 2, follow: { min: 3, max: 8 }, category: "interested", sub: "Demo Request",
    summary: "{lead} leads outbound for a {industry} team of about twelve reps who research accounts by hand across spreadsheets and LinkedIn; the pain is knowing which accounts to work each week. {rep} walked through how Signal scores accounts against the ICP, and a 30-minute demo with their sales ops manager is set for next week.",
    note: "12 reps, research done by hand. Demo with sales ops manager booked.",
    msg: "Hi {first}, great speaking with you just now. As discussed, I'll send the invite for the demo with your sales ops manager. Anything you want covered, let me know here.",
    lines: [
      rep("Hi {lead}, it's {rep} from Northwind. You asked for a demo on our site this morning, is now an okay time for a few minutes?"),
      lead("Oh hi {rep}, yes. I've got about ten minutes before my next meeting."),
      rep("Perfect, I'll be quick. What made you look at Signal in the first place?"),
      lead("Honestly, our reps spend half their week researching accounts. We've got twelve people on the team and everybody has their own spreadsheet."),
      rep("That's very common. When you say research, what does that look like day to day?"),
      lead("They pull a list out of HubSpot, then go through LinkedIn and the company site to work out who's worth contacting. It takes maybe twenty minutes per account."),
      rep("And how do they decide which accounts to work first?"),
      lead("Gut feel, mostly. We have an ICP document but nobody really scores against it."),
      rep("Got it. So two problems: the time per account, and no consistent way to prioritise."),
      lead("Exactly. Management keeps asking why our first-meeting numbers are flat even though activity is up."),
      rep("That's what Signal is built for. It scores every account against your ICP, and every Monday your reps see the accounts to contact that week and why. Teams like Brightloop cut research time by about seventy percent."),
      lead("Seventy percent would be huge. How does it get the data? Does it replace HubSpot?"),
      rep("No, it sits on top. It syncs both ways with HubSpot, so reps stay where they already work."),
      lead("Okay, that's a relief. We just finished a painful HubSpot migration."),
      rep("Understood. Who else would need to see this besides you?"),
      lead("Our sales ops manager. She'd be the one setting it up, so she should be on the demo."),
      rep("Great. I can do thirty minutes next Tuesday or Wednesday afternoon. Which suits you both?"),
      lead("Wednesday after two works. Send it to my work email and I'll forward it."),
      rep("Done. I'll send an invite for Wednesday at 2:30 with a short agenda."),
      lead("Perfect. Thanks, {rep}."),
      rep("Thank you {lead}, talk Wednesday."),
    ],
  },
  {
    key: "existing-tool",
    c: 9, d: 3, follow: { min: 12, max: 16 }, category: "interested", sub: "Information Requested",
    summary: "{lead} already runs outbound on a sequencing platform and was wary of adding another tool. {rep} explained that Signal sits in front of the sequencer rather than replacing it; {lead} will read a one-page comparison and asked to be contacted again in two weeks.",
    note: "Happy with their sequencer. Sent comparison, check back in two weeks.",
    msg: "Hi {first}, great speaking with you just now. As discussed, here's the one-page comparison: northwind.example/signal-vs-sequencers.pdf. I'll check back in two weeks.",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. We exchanged messages last week about Signal. Do you have two minutes?"),
      lead("I do, but I'll be honest, we already have a sequencing platform and the team is happy with it."),
      rep("That's fair, and I'm not suggesting you replace it. Can I ask what you use it for?"),
      lead("Sequences, mostly. Email cadences and some call tasks."),
      rep("Right. Those tools are great at running the cadence. Signal helps with the step before: which accounts should go into those sequences in the first place."),
      lead("We build those lists from exports."),
      rep("And how often does a list turn out to be mostly accounts that never reply?"),
      lead("More often than I'd like. Probably half of them."),
      rep("That's the gap. Signal scores accounts against your best customers so the sequencer only gets the ones worth working. Most customers keep their existing tools."),
      lead("Hm. I'm wary of adding yet another login for the reps."),
      rep("Reasonable. The scores and the weekly list can be pushed into your sequencer or Slack, so reps don't need to log into Signal at all."),
      lead("That changes things a bit. Do you have something I can show my VP?"),
      rep("I'll send a one-page comparison today, plus a short example from a team with a similar setup."),
      lead("Send it over and I'll look. Can you check back in a couple of weeks? We're mid-quarter."),
      rep("Of course. I'll message you in two weeks. Thanks for being straight with me, {lead}."),
      lead("No problem. Talk soon."),
    ],
  },
  {
    key: "pricing",
    c: 10, d: 5, follow: { min: 2, max: 5 }, category: "interested", sub: "Information Requested",
    summary: "{lead} wanted pricing for a team of about fifteen and whether annual billing and a pilot are available. {rep} covered the Starter and Team plans, the 15% annual discount and the two-seat free pilot; {lead} will take the numbers to their finance lead and asked for a written quote.",
    note: "15 seats, Team plan. Quote requested, finance lead decides this week.",
    msg: "Hi {first}, thanks for the chat. Here's the written quote for 15 seats on the Team plan, with the pilot outline: northwind.example/quote",
    lines: [
      rep("Hi {lead}, {rep} at Northwind, returning your call about pricing."),
      lead("Thanks for calling back. I just need ballpark numbers before I bring anyone else in."),
      rep("Sure. How many reps would be using it?"),
      lead("About fifteen, maybe eighteen by the end of the year."),
      rep("Then you'd want the Team plan. It's 129 dollars per seat per month, and that includes the shared inbox, CRM sync and up to twenty-five thousand accounts."),
      lead("So roughly two thousand a month."),
      rep("About 1,935 for fifteen seats. On an annual contract it drops by fifteen percent."),
      lead("Okay. And is there a way to try it before we commit? Finance will ask."),
      rep("Yes. We run a fourteen-day pilot with two seats free on one campaign. Most teams use it to compare against their current process."),
      lead("That's helpful. What does the Starter plan cover? Maybe we start smaller."),
      rep("Starter is 49 per seat, up to a thousand accounts tracked, without the shared inbox or CRM sync. For fifteen reps, people usually outgrow it quickly."),
      lead("I thought so. Can you put the Team numbers in writing?"),
      rep("I'll send a written quote and a pilot outline this afternoon."),
      lead("Great. I'll take it to our finance lead on Thursday."),
      rep("Perfect. I'll check in Friday to see what she thinks."),
      lead("Sounds good, thanks."),
    ],
  },
  {
    key: "book-demo",
    c: 8, d: 5, follow: { min: 2, max: 5 }, category: "interested", sub: "Demo Request",
    summary: "{lead} had watched the recorded walkthrough and had two questions about CRM sync and alert settings. {rep} answered both and booked a live demo for {lead}'s team on Thursday at 3pm.",
    note: "Watched the walkthrough. Live demo for the team booked Thursday 3pm.",
    msg: "Hi {first}, thanks for your time today. Confirming our demo on Thursday at 3pm, invite is on its way.",
    lines: [
      rep("Hi {lead}, it's {rep} from Northwind. Did you get a chance to watch the walkthrough I sent?"),
      lead("I did, yes. Two questions. Does the CRM sync write back to HubSpot, or only read?"),
      rep("Both ways. Scores and the reason for each account land on the HubSpot record, and changes you make there flow back."),
      lead("Good. And can we control which alerts reps get? I don't want them buried."),
      rep("Yes, you set thresholds per team. Most customers start with the top ten accounts a week per rep."),
      lead("Okay, that's what I wanted to hear. I'd like my team leads to see it live."),
      rep("Happy to. How about Thursday at 3pm? Thirty minutes."),
      lead("Thursday at 3 works. I'll add two of them."),
      rep("Perfect, I'll send the invite now. Anything specific you want covered?"),
      lead("Alerts and the Slack part, mainly."),
      rep("Noted. Speak Thursday, {lead}."),
    ],
  },
  {
    key: "next-week",
    c: 3, d: 2, follow: { min: 3, max: 7 }, category: "interested", sub: "Meeting Requested",
    summary: "{lead} was travelling and could not talk; they asked {rep} to call back early next week. {rep} agreed to try Tuesday morning.",
    note: "Travelling. Call back Tuesday morning.",
    msg: "Hi {first}, no problem at all. I'll call you Tuesday morning as agreed.",
    lines: [
      rep("Hi {lead}, it's {rep} from Northwind, is this a bad moment?"),
      lead("Hi {rep}, yes, I'm at the airport. Can you call me next week instead?"),
      rep("Of course. Would Tuesday morning suit you?"),
      lead("Tuesday morning is good. Around ten."),
      rep("Ten on Tuesday, I'll call then. Safe travels."),
      lead("Thanks, speak then."),
    ],
  },
  {
    key: "security",
    c: 6, d: 2, follow: { min: 5, max: 12 }, category: "interested", sub: "Information Requested",
    summary: "{lead} is evaluating Signal for a {industry} team that needs a security review first. {rep} covered SOC 2 Type II, per-customer workspace isolation and the DPA; the security pack goes to {lead} today and review normally takes about two weeks.",
    note: "Needs security review first. Pack sent, review takes ~2 weeks.",
    msg: "Hi {first}, great speaking with you just now. As discussed, here's the security pack and DPA: northwind.example/security",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. You asked about data privacy, do you have a few minutes?"),
      lead("Yes. We're in {industry}, so security review is the long pole for us. Where is our data stored?"),
      rep("Each customer gets an isolated workspace. Data sits in the region you choose, US or EU, encrypted at rest and in transit."),
      lead("And who on your side can access it?"),
      rep("Only a small group of support engineers, and only with a time-limited grant you can see in the audit log."),
      lead("Do you have SOC 2?"),
      rep("Yes, Type II. I can send the report, the DPA and our subprocessor list today."),
      lead("That would help. Our security team usually takes a couple of weeks."),
      rep("That's typical. If they have questions, I can get them on a call with our security lead."),
      lead("Good to know. Send the pack and I'll start the process."),
      rep("Will do. I'll check in once they've had a look."),
      lead("Thanks {rep}."),
    ],
  },
  {
    key: "not-interested",
    c: 34, d: 18, done: true, endsCall: true, follow: { min: 0, max: 0 }, category: "not_interested", sub: "Not Required Right Now",
    summary: "{lead} said {company} is not looking at new tools this year and asked not to be chased. The call ended politely.",
    note: "Not looking at new tools this year. Do not chase.",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. You'd replied to our note, is this a good moment?"),
      lead("Hi. Yes, but I should say upfront that we're not looking at new tools this year."),
      rep("Understood. Is it budget, or is outbound just not a focus right now?"),
      lead("Both. We're consolidating what we have, and nothing new gets approved until next fiscal year."),
      rep("That makes sense. If it's alright, I'll leave it there and not chase you."),
      lead("I'd appreciate that. Thanks for understanding."),
      rep("Of course. Good luck with the year, {lead}."),
    ],
  },
  {
    key: "hiring-freeze",
    c: 24, d: 13, done: true, endsCall: true, follow: { min: 0, max: 0 }, category: "not_interested", sub: "Not Required Right Now",
    summary: "{lead} liked the idea but {company} has a hiring and tooling freeze until next fiscal year. {rep} agreed to check back in the new year.",
    note: "Freeze until next fiscal year. Check back in January.",
    msg: "Hi {first}, thanks for being upfront today. I'll check back in January.",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. Thanks for taking the call. Where does Signal sit on your list right now?"),
      lead("Honestly, it's interesting, but we're under a freeze. No new tools until the new fiscal year."),
      rep("Understood. Is the freeze across the board, or only for new headcount?"),
      lead("Everything. Even renewals are being scrutinised."),
      rep("That's useful to know. Would it be okay if I checked back with you in January, once budgets are set?"),
      lead("Sure, that works. Message me then."),
      rep("Will do. Thanks for your honesty, {lead}."),
    ],
  },
  {
    key: "locked-in",
    c: 18, d: 10, done: true, endsCall: true, follow: { min: 0, max: 0 }, category: "not_interested", sub: "Already Using a Tool — Not Required",
    summary: "{lead} signed a two-year contract with another platform last spring and does not plan to switch. {rep} left the door open for when the contract nears renewal.",
    note: "In a two-year contract with another vendor. Revisit near renewal.",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. Do you have a moment to talk about how {company} prioritises accounts?"),
      lead("I'll save you some time: we signed a two-year deal with another platform last spring."),
      rep("Thanks for being direct. Does it cover account scoring, or mainly sequencing?"),
      lead("Both, more or less. It's not perfect but the team is used to it."),
      rep("Understood. If it's alright, I'll check in a few months before the renewal."),
      lead("Fine by me, but don't expect a different answer."),
      rep("Fair enough. Thanks for your time, {lead}."),
    ],
  },
  {
    key: "budget",
    c: 6, d: 1, follow: { min: 6, max: 10 }, category: "interested", sub: "Information Requested",
    summary: "{lead} likes the approach and would champion it, but needs sign-off from finance and new-tool budget opens in January. {rep} suggested a two-seat pilot now so results are ready for the budget conversation; {lead} will ask their manager and reply next week.",
    note: "Champion, but budget opens in January. Pilot proposed, replying next week.",
    msg: "Hi {first}, thanks for your time today. Here's the two-seat pilot outline we talked about: northwind.example/pilot",
    lines: [
      rep("Hi {lead}, it's {rep} from Northwind. Thanks for making time."),
      lead("Of course. I've been looking at Signal since the demo and the team likes it."),
      rep("Good to hear. What did they like most?"),
      lead("The weekly account list. Our reps never agree on who to call first, and that settles it."),
      rep("That's one of the things customers mention most. What's the next step on your side?"),
      lead("Honestly, budget. I'd champion it, but new-tool spend needs the CFO, and that opens up in January."),
      rep("That's helpful to know. Would it help to have results to show when that conversation happens?"),
      lead("Definitely. But we can't buy anything yet."),
      rep("You wouldn't need to. We run a free two-seat pilot for fourteen days on one campaign. You'd have numbers before January."),
      lead("That's interesting. Who would need to approve a pilot?"),
      rep("Usually nobody beyond a manager, since it's free and uses one campaign."),
      lead("Then I'd ask my manager. Which data would you need from us?"),
      rep("Just a CRM connection and one list of accounts. Setup takes an afternoon."),
      lead("Okay. Let me check with her this week and come back to you."),
      rep("Perfect. I'll send a one-page pilot outline so you have something to forward."),
      lead("That would help a lot."),
      rep("Sending it now. Speak next week, {lead}."),
    ],
  },
  {
    key: "wrong-person",
    c: 4, d: 0, done: true, endsCall: true, follow: { min: 0, max: 0 }, category: "other", sub: "Connected to Different POC",
    summary: "{lead} does not own sales tooling at {company}; their Head of Sales Ops does. {lead} agreed to introduce {rep} by email.",
    note: "Not the owner. Intro to Head of Sales Ops promised by email.",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. I believe you look after sales tooling at {company}?"),
      lead("Not anymore, that moved to our Head of Sales Ops a few months ago. I can introduce you if you like."),
      rep("That would be great. Is email the best way?"),
      lead("Yes, I'll copy you on a note this afternoon."),
      rep("Thank you {lead}, I appreciate it."),
    ],
  },
  {
    key: "busy-callback",
    c: 3, d: 2, follow: { min: 1, max: 3 }, category: "interested", sub: "Meeting Requested",
    summary: "{lead} picked up between meetings and could only talk for a minute; they asked {rep} to call tomorrow afternoon.",
    msg: "Hi {first}, no worries, I'll call you tomorrow afternoon as agreed.",
    lines: [
      rep("Hi {lead}, it's {rep} from Northwind. Is this a bad time?"),
      lead("Hi {rep}. I'm literally walking into a meeting. Can you try me tomorrow afternoon?"),
      rep("Sure thing, around three?"),
      lead("Three is fine. Talk then."),
    ],
  },
  {
    key: "send-details",
    c: 4, d: 3, follow: { min: 2, max: 5 }, category: "interested", sub: "Information Requested",
    summary: "{lead} was interested in a quick overview and asked for details by WhatsApp rather than email. {rep} will send a one-pager and the pilot terms today.",
    msg: "Hi {first}, thanks for the chat. Here's the overview I mentioned: northwind.example/signal-overview.pdf",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. Thanks for picking up. I'll keep it short."),
      lead("Hi. I only have a minute. What's this about exactly?"),
      rep("Signal tells your sales team which accounts to contact each week and why. You'd replied to our message and I wanted to see if it's worth a longer chat."),
      lead("Sounds relevant. Can you just send me the details? I'll read it tonight."),
      rep("Absolutely. WhatsApp or email?"),
      lead("WhatsApp is easier."),
      rep("Sending it right after this call. I'll check in on Friday."),
      lead("Sounds good, thanks."),
    ],
  },
  {
    key: "trial-expansion",
    c: 0, d: 8, follow: { min: 3, max: 5 }, category: "interested", sub: "Trial User",
    summary: "{lead}'s team has used the free pilot for ten days with four active users and likes the weekly account list. {rep} proposed moving to the Team plan with eight seats before the pilot ends; {lead} will confirm with their VP by Friday.",
    note: "Pilot going well, 4 active users. Proposed 8 seats on Team, VP decides by Friday.",
    msg: "Hi {first}, great speaking with you just now. As discussed, here's the 8-seat Team quote: northwind.example/quote",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. I wanted to check in on the pilot. How's it going?"),
      lead("Pretty well, actually. Four of us use it every day now."),
      rep("That's great to hear. What's working best?"),
      lead("The Monday list. Our reps stopped arguing about who to call, and two of them booked meetings off it in the first week."),
      rep("Love that. Is there anything that's frustrating?"),
      lead("Not really. Maybe the Slack alerts, but that's minor."),
      rep("We can tune those, I'll show you after. Since the pilot ends next week, have you thought about what comes next?"),
      lead("We'd like to keep it. I think we'd want more seats, the rest of the team keeps asking."),
      rep("How many are you thinking?"),
      lead("Eight, probably. Four now and four more once we've trained them."),
      rep("Eight seats on the Team plan is about a thousand a month, and annual billing takes fifteen percent off."),
      lead("That's in the range I expected. I need my VP to approve it."),
      rep("Understood. I'll send a quote you can forward. Could you get an answer by Friday so you don't lose pilot data?"),
      lead("Yes, I'll push for Friday."),
      rep("Perfect. I'll also set up the Slack alert thresholds with you this week."),
      lead("Thanks {rep}, I appreciate it."),
    ],
  },
  {
    key: "trial-feedback",
    c: 0, d: 6, follow: { min: 5, max: 8 }, category: "interested", sub: "Trial User",
    summary: "{lead} shared pilot feedback: scoring is accurate but Slack alerts are too noisy. {rep} showed how to tune thresholds and promised a follow-up on the alert settings; they agreed to check in again next week.",
    note: "Scores accurate, Slack alerts too noisy. Tuning thresholds, check in next week.",
    msg: "Hi {first}, thanks for the feedback today. I've tightened the alert threshold on your workspace, tell me if it feels better.",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. Do you have a few minutes to share how the pilot is going?"),
      lead("Sure. Overall good. The scoring is better than I expected, our reps agree with it about eight times out of ten."),
      rep("That's a strong number. What about the other two?"),
      lead("Usually small companies that score high because of one signal. It's not a big deal."),
      rep("I can show you how to weight that signal down. Anything else?"),
      lead("The Slack alerts. They're too noisy, people started muting the channel."),
      rep("Good to know. By default it alerts on anything over seventy, but you can raise that per team."),
      lead("Can you do it for us? I'd rather not click around."),
      rep("Of course, I'll change it on your workspace today and set it to the top ten a week per rep."),
      lead("Perfect, that's what we need."),
      rep("Let's talk again next week to see if it's quieter."),
      lead("Sounds good."),
    ],
  },
  {
    key: "won-expansion",
    c: 0, d: 4, done: true, endsCall: true, follow: { min: 0, max: 0 }, category: "customer", sub: "Customer",
    summary: "{lead} confirmed that {company} wants to move from the pilot to the Team plan with eight seats. {rep} will send the order form today and schedule onboarding for next week.",
    note: "Confirmed: Team plan, 8 seats, annual. Order form sent, onboarding next week.",
    msg: "Hi {first}, great news and thank you! Order form is on its way, onboarding invite to follow.",
    lines: [
      rep("Hi {lead}, {rep} from Northwind. I was hoping you'd have news from your VP."),
      lead("I do. She approved it. We want to move to the Team plan with eight seats."),
      rep("That's wonderful news. Annual billing, to get the fifteen percent off?"),
      lead("Yes, annual. Please send the order form and I'll get it signed."),
      rep("I'll send it this afternoon. After that I'd like to book onboarding for next week so the extra four reps are productive straight away."),
      lead("Perfect. Tuesday or Wednesday would work for the team."),
      rep("Wednesday it is, I'll send the invite. Thank you {lead}, really glad it worked out."),
      lead("Thanks {rep}, talk soon."),
    ],
  },
];

const WRONG_NUMBER: Scenario = {
  key: "wrong-number",
  c: 0, d: 0, done: true, endsCall: true, follow: { min: 0, max: 0 }, category: "other", sub: "Other",
  summary: "The person who answered said {lead} no longer uses this number. {rep} apologised and ended the call.",
  lines: [
    rep("Hi, is that {lead}?"),
    lead("No, sorry, I think you have the wrong number. I've had this one for a year."),
    rep("Apologies for the disturbance, I'll update our records."),
  ],
};
