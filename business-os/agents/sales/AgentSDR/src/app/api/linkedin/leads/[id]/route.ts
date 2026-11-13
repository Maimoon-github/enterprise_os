import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, asc, eq, ne } from "drizzle-orm";
import { invitationMessageLengthError, isInvitationMessageTooLong } from "@/lib/linkedin/invitationMessage";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import {
  campaigns,
  connections,
  leads,
  linkedInAccounts,
  messages,
} from "@/lib/linkedin/schema";
import { companies, people } from "@/lib/leads/schema";
import { personProfile, personVariables } from "@/lib/leads/variables";
import { renderLeadTemplates } from "@/lib/linkedin/renderLeadTemplates";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(_req, async () => {
    const { id } = await params;

    // Prisma's `include` of campaign / linkedInAccount / connection becomes three
    // left joins (every one of those FKs is nullable); messages is a separate
    // ordered query.
    const [row] = await db
      .select({
        lead: leads,
        person: people,
        company: companies,
        campaign: {
          id: campaigns.id,
          name: campaigns.name,
          invitationMessage: campaigns.invitationMessage,
          acceptanceMessage: campaigns.acceptanceMessage,
          followUp1Message: campaigns.followUp1Message,
          followUp2Message: campaigns.followUp2Message,
          followUp3Message: campaigns.followUp3Message,
        },
        linkedInAccount: {
          id: linkedInAccounts.id,
          username: linkedInAccounts.username,
          name: linkedInAccounts.name,
          profilePictureUrl: linkedInAccounts.profilePictureUrl,
        },
        connection: {
          id: connections.id,
          chatId: connections.chatId,
          connectedAt: connections.connectedAt,
        },
      })
      .from(leads)
      .leftJoin(people, eq(leads.personId, people.id))
      .leftJoin(companies, eq(people.companyId, companies.id))
      .leftJoin(campaigns, eq(leads.campaignId, campaigns.id))
      .leftJoin(linkedInAccounts, eq(leads.linkedinAccountId, linkedInAccounts.id))
      .leftJoin(connections, eq(connections.leadId, leads.id))
      .where(and(inOrg(leads), eq(leads.id, id)))
      .limit(1);

    if (!row) {
      return NextResponse.json({ ok: false, error: "Lead not found" }, { status: 404 });
    }

    const lead = row.lead;
    const profile = row.person ? personProfile(row.person, row.company) : {
      linkedinUrl: lead.sourceLinkedinIdentifier,
      name: lead.name,
      profilePictureUrl: lead.profilePictureUrl,
      headline: lead.headline,
      location: lead.location,
    };
    const campaign = row.campaign?.id ? row.campaign : null;
    const linkedInAccount = row.linkedInAccount?.id ? row.linkedInAccount : null;
    const connection = row.connection?.id ? row.connection : null;
    const variables = row.person ? personVariables(row.person, row.company) : {};
    const templates = {
      invitationMessage: campaign?.invitationMessage ?? lead.invitationMessage,
      acceptanceMessage: campaign?.acceptanceMessage ?? lead.acceptanceMessage,
      followUp1Message: campaign?.followUp1Message ?? lead.followUp1Message,
      followUp2Message: campaign?.followUp2Message ?? lead.followUp2Message,
      followUp3Message: campaign?.followUp3Message ?? lead.followUp3Message,
    };
    const renderedTemplates = renderLeadTemplates(
      templates,
      variables,
    );

    const leadMessages = await db
      .select({
        id: messages.id,
        type: messages.type,
        text: messages.text,
        seen: messages.seen,
        createdAt: messages.createdAt,
      })
      .from(messages)
      .where(and(inOrg(messages), eq(messages.leadId, lead.id)))
      .orderBy(asc(messages.createdAt));

    // Other Lead rows for the same person: which other campaigns they're in, and
    // (for contacted ones) which accounts are excluded from ever sending to them again.
    const siblings = lead.personId ? await db
      .select({
        status: leads.status,
        campaignId: campaigns.id,
        campaignName: campaigns.name,
        accountId: linkedInAccounts.id,
        accountUsername: linkedInAccounts.username,
        accountName: linkedInAccounts.name,
        accountProfilePictureUrl: linkedInAccounts.profilePictureUrl,
      })
      .from(leads)
      .leftJoin(campaigns, eq(leads.campaignId, campaigns.id))
      .leftJoin(linkedInAccounts, eq(leads.linkedinAccountId, linkedInAccounts.id))
      .where(and(inOrg(leads), eq(leads.personId, lead.personId), ne(leads.id, lead.id))) : [];

    const alsoInCampaigns = [
      ...new Map(
        siblings
          .filter((s) => s.campaignId !== null)
          .map((s) => [s.campaignId!, { id: s.campaignId!, name: s.campaignName! }])
      ).values(),
    ];
    const excludedAccounts = [
      ...new Map(
        siblings
          .filter((s) => s.status !== "PENDING" && s.accountId !== null)
          .map((s) => [
            s.accountId!,
            {
              id: s.accountId!,
              username: s.accountUsername!,
              name: s.accountName,
              profilePictureUrl: s.accountProfilePictureUrl,
            },
          ])
      ).values(),
    ];

    return NextResponse.json({
      ok: true,
      lead: {
        id: lead.id,
        linkedinUrl: profile.linkedinUrl,
        providerId: lead.providerId,
        name: profile.name,
        profilePictureUrl: profile.profilePictureUrl,
        headline: profile.headline,
        location: profile.location,
        status: lead.status,
        inviteRetryCount: lead.inviteRetryCount,
        ...templates,
        renderedTemplates,
        requestSentAt: lead.requestSentAt?.toISOString() ?? null,
        acceptMessageSentAt: lead.acceptMessageSentAt?.toISOString() ?? null,
        followUp1SentAt: lead.followUp1SentAt?.toISOString() ?? null,
        followUp2SentAt: lead.followUp2SentAt?.toISOString() ?? null,
        followUp3SentAt: lead.followUp3SentAt?.toISOString() ?? null,
        createdAt: lead.createdAt.toISOString(),
        updatedAt: lead.updatedAt.toISOString(),
        campaign,
        linkedInAccount,
        connection: connection
          ? {
              id: connection.id,
              chatId: connection.chatId,
              connectedAt: connection.connectedAt?.toISOString() ?? null,
            }
          : null,
        messages: leadMessages.map((m) => ({
          ...m,
          createdAt: m.createdAt.toISOString(),
        })),
        alsoInCampaigns,
        excludedAccounts,
      },
    });
  });
}

const MESSAGE_FIELDS = [
  "invitationMessage",
  "acceptanceMessage",
  "followUp1Message",
  "followUp2Message",
  "followUp3Message",
] as const;

type MessageField = (typeof MESSAGE_FIELDS)[number];

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(req, async () => {
    const { id } = await params;
    try {
      const body = await req.json();
      const allowed = MESSAGE_FIELDS;
      const data: Partial<Record<MessageField, string | null>> = {};
      // Trim on write: a whitespace-only message must be stored as null, otherwise it
      // reads as "has a message" at send time and delivers a blank follow-up.
      for (const key of allowed) {
        if (key in body) {
          const value = typeof body[key] === "string" ? body[key].trim() : body[key];
          data[key] = value || null;
        }
      }
      if (
        "invitationMessage" in data &&
        isInvitationMessageTooLong(data.invitationMessage)
      ) {
        return NextResponse.json(
          {
            ok: false,
            error: invitationMessageLengthError(
              (data.invitationMessage ?? "").length
            ),
          },
          { status: 400 }
        );
      }
      // Drizzle rejects an empty `set`; Prisma accepted `data: {}` as a no-op
      // update, so fall back to reading the row when nothing was sent.
      const [nativeLead] = await db.select().from(leads).where(and(inOrg(leads), eq(leads.id, id))).limit(1);
      if (!nativeLead) {
        return NextResponse.json({ ok: false, error: "Lead not found" }, { status: 404 });
      }
      if (!nativeLead.campaignId) {
        return NextResponse.json({ ok: false, error: "Lead has no campaign" }, { status: 400 });
      }
      if (Object.keys(data).length) {
        await db.update(campaigns).set({ ...data, updatedAt: new Date() }).where(and(inOrg(campaigns), eq(campaigns.id, nativeLead.campaignId)));
      }
      const [campaignMessages] = await db.select({
        invitationMessage: campaigns.invitationMessage,
        acceptanceMessage: campaigns.acceptanceMessage,
        followUp1Message: campaigns.followUp1Message,
        followUp2Message: campaigns.followUp2Message,
        followUp3Message: campaigns.followUp3Message,
      }).from(campaigns).where(and(inOrg(campaigns), eq(campaigns.id, nativeLead.campaignId))).limit(1);
      const lead = { ...nativeLead, ...campaignMessages };
      if (!lead) {
        return NextResponse.json({ ok: false, error: "Lead not found" }, { status: 404 });
      }
      return NextResponse.json({ ok: true, lead });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(_req, async () => {
    const { id } = await params;
    try {
      await db.delete(leads).where(and(inOrg(leads), eq(leads.id, id)));
      return NextResponse.json({ ok: true });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
