/**
 * Builds the Apollo People-Search URL that is the final deliverable of a campaign:
 * one link encoding every qualified domain + the target job titles.
 *
 * NOTE: Apollo's query-param names have changed across UI versions. They are
 * centralised here so the exact format can be confirmed/tweaked in one place.
 */

export const APOLLO_LINK_PARAMS = {
  base: "https://app.apollo.io/#/people",
  /** repeated per job title */
  title: "personTitles[]",
  /** repeated per organization domain */
  orgDomain: "qOrganizationDomains[]",
  page: "page",
} as const;

export function buildApolloPeopleSearchUrl(opts: {
  domains: string[];
  titles?: string[];
}): string {
  const params = new URLSearchParams();
  params.set(APOLLO_LINK_PARAMS.page, "1");
  for (const title of opts.titles ?? []) {
    params.append(APOLLO_LINK_PARAMS.title, title);
  }
  for (const domain of opts.domains) {
    params.append(APOLLO_LINK_PARAMS.orgDomain, domain);
  }
  return `${APOLLO_LINK_PARAMS.base}?${params.toString()}`;
}
