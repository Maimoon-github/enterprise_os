export const MAX_INVITATION_MESSAGE_LENGTH = 300;

export const invitationMessageLength = (message: string | null | undefined): number =>
  (message ?? "").length;

export const isInvitationMessageTooLong = (message: string | null | undefined): boolean =>
  invitationMessageLength(message) > MAX_INVITATION_MESSAGE_LENGTH;

export const invitationMessageLengthError = (length: number): string =>
  `Invitation message is ${length} characters (max ${MAX_INVITATION_MESSAGE_LENGTH})`;

export const invitationMessageTooLongError = (
  identifier: string,
  message: string | null | undefined
): string =>
  `${identifier}: ${invitationMessageLengthError(invitationMessageLength(message))}`;
