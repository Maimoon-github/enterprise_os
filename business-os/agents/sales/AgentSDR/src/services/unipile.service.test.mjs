import { describe, expect, test } from "bun:test";
import { invitationResponseId, mapLinkedinProfile } from "./unipile.service.ts";

describe("Unipile LinkedIn profile mapping", () => {
  test("maps canonical People fields and retains the full provider payload", () => {
    const raw = {
      provider_id: "provider-123",
      public_identifier: "Pat-Lee",
      first_name: "Pat",
      last_name: "Lee",
      headline: "Generic headline",
      location: "Singapore",
      profile_picture_url: "https://example.com/pat.jpg",
      contact_info: { emails: ["PAT@EXAMPLE.COM"], phones: ["+6512345678"] },
      work_experience: [
        { position: "VP Sales", company: "Acme", current: true },
        { position: "Director", company: "Old Co", current: false },
      ],
      skills: [{ name: "Sales", endorsement_count: 5 }],
    };

    expect(mapLinkedinProfile(raw)).toMatchObject({
      providerId: "provider-123",
      publicIdentifier: "pat-lee",
      email: "pat@example.com",
      firstName: "Pat",
      lastName: "Lee",
      headline: "Generic headline",
      currentTitle: "VP Sales",
      currentCompanyName: "Acme",
      location: "Singapore",
      profilePictureUrl: "https://example.com/pat.jpg",
      leadData: raw,
    });
  });

  test("requires the provider id needed by LinkedIn sending", () => {
    expect(() => mapLinkedinProfile({ public_identifier: "pat-lee" })).toThrow("provider_id");
  });

  test("maps object-shaped contact emails returned by profile sections", () => {
    expect(mapLinkedinProfile({
      provider_id: "provider-456",
      public_identifier: "pat-lee",
      contact_info: { emails: [{ type: "work", value: "PAT@EXAMPLE.COM" }] },
    }).email).toBe("pat@example.com");
  });
});

describe("Unipile invitation response mapping", () => {
  test("reads the current invitation_id response field", () => {
    expect(invitationResponseId({ object: "UserInvitationSent", invitation_id: "invite-123" })).toBe("invite-123");
  });

  test("keeps compatibility with older response aliases", () => {
    expect(invitationResponseId({ id: "legacy-id" })).toBe("legacy-id");
    expect(invitationResponseId({ message_id: "legacy-message-id" })).toBe("legacy-message-id");
  });

  test("returns null when the provider response has no identifier", () => {
    expect(invitationResponseId({ object: "UserInvitationSent" })).toBeNull();
  });
});
