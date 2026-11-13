import { describe, expect, test } from "bun:test";
import {
  bareWhatsappJid,
  isWhatsappGroupId,
  phoneFromProviderId,
  whatsappAccountPhone,
  whatsappAccountStatus,
  whatsappProviderId,
} from "./unipile.whatsapp";

describe("WhatsApp provider ids", () => {
  test("a number becomes its WhatsApp id and back", () => {
    expect(whatsappProviderId("+91 98765-43210")).toBe("919876543210@s.whatsapp.net");
    expect(phoneFromProviderId("919876543210@s.whatsapp.net")).toBe("+919876543210");
  });

  test("a device suffix is dropped", () => {
    expect(phoneFromProviderId("919876543210:12@s.whatsapp.net")).toBe("+919876543210");
    expect(bareWhatsappJid("919876543210:12@s.whatsapp.net")).toBe("919876543210@s.whatsapp.net");
    expect(bareWhatsappJid(" 919876543210@S.WHATSAPP.NET ")).toBe("919876543210@s.whatsapp.net");
    expect(bareWhatsappJid("")).toBeNull();
  });

  test("groups, privacy ids and junk carry no number", () => {
    expect(phoneFromProviderId("120363025246@g.us")).toBeNull();
    expect(phoneFromProviderId("207716110643219@lid")).toBeNull();
    expect(phoneFromProviderId("123@s.whatsapp.net")).toBeNull();
    expect(phoneFromProviderId(null)).toBeNull();
    expect(isWhatsappGroupId("120363025246@g.us")).toBe(true);
    expect(isWhatsappGroupId("919876543210@s.whatsapp.net")).toBe(false);
    expect(isWhatsappGroupId(undefined)).toBe(false);
  });
});

describe("whatsappAccountStatus", () => {
  test("maps Unipile's source statuses", () => {
    expect(whatsappAccountStatus("OK")).toBe("connected");
    expect(whatsappAccountStatus("running")).toBe("connected");
    expect(whatsappAccountStatus("CONNECTING")).toBe("connected");
    expect(whatsappAccountStatus("CREDENTIALS")).toBe("credentials");
    expect(whatsappAccountStatus("STOPPED")).toBe("disconnected");
    expect(whatsappAccountStatus("DISCONNECTED")).toBe("disconnected");
    expect(whatsappAccountStatus("ERROR")).toBe("error");
    expect(whatsappAccountStatus(undefined)).toBe("error");
  });
});

describe("whatsappAccountPhone", () => {
  test("reads the number from connection_params.im", () => {
    expect(whatsappAccountPhone({ connection_params: { im: { phone_number: "+91 98765 43210" } } })).toBe("+919876543210");
    expect(whatsappAccountPhone({ connection_params: { im: { id: "919876543210:3@s.whatsapp.net" } } })).toBe("+919876543210");
    expect(whatsappAccountPhone({ name: "919876543210", connection_params: {} })).toBe("+919876543210");
    expect(whatsappAccountPhone({ name: "Sales team" })).toBeNull();
  });
});
