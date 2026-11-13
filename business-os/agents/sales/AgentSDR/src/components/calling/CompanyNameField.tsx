"use client";

import { useEffect, useId, useRef, useState } from "react";
import * as Input from "@/components/alignui/input";
import * as Popover from "@/components/alignui/popover";
import { CompanyFavicon } from "@/components/calling/callingShared";
import type { CompanySuggestion } from "@/lib/leads/records";
import { cn } from "@/utils/cn";

/**
 * The calling modals' company-name input, with a type-ahead over the
 * organization's companies. Picking one hands the whole company to `onPick`,
 * so the caller can fill the website from its domain; typing a name that is
 * not there behaves like a plain text field.
 */
export function CompanyNameField({
  label,
  value,
  onChange,
  onPick,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onPick: (company: CompanySuggestion) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const listId = `${id}-list`;
  const anchorRef = useRef<HTMLDivElement>(null);
  // Only what the person types is searched — a prefilled or picked name is not.
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<CompanySuggestion[]>([]);
  const [focused, setFocused] = useState(false);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const term = query.trim();
    if (!term) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetch(`/api/leads/companies/suggest?q=${encodeURIComponent(term)}`, { signal: controller.signal })
        .then((response) => (response.ok ? response.json() : { companies: [] }))
        .then((body: { companies?: CompanySuggestion[] }) => {
          setSuggestions(body.companies ?? []);
          setActive(0);
        })
        .catch(() => {});
    }, 150);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const open = focused && !disabled && suggestions.length > 0;

  const pick = (company: CompanySuggestion) => {
    setQuery("");
    setSuggestions([]);
    onPick(company);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((index) => (index + step + suggestions.length) % suggestions.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      pick(suggestions[active]);
    }
  };

  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-label-sm text-text-strong-950">{label}</label>
      <Popover.Root open={open} onOpenChange={(next) => { if (!next) setSuggestions([]); }}>
        <Popover.Anchor asChild>
          <div ref={anchorRef}>
            <Input.Root size="small">
              <Input.Wrapper>
                <Input.Input
                  id={id}
                  value={value}
                  disabled={disabled}
                  autoComplete="off"
                  role="combobox"
                  aria-expanded={open}
                  aria-controls={listId}
                  aria-autocomplete="list"
                  aria-activedescendant={open ? `${listId}-${active}` : undefined}
                  onChange={(event) => {
                    onChange(event.target.value);
                    setQuery(event.target.value);
                    if (!event.target.value.trim()) setSuggestions([]);
                  }}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  onKeyDown={onKeyDown}
                />
              </Input.Wrapper>
            </Input.Root>
          </div>
        </Popover.Anchor>
        <Popover.Content
          unstyled
          showArrow={false}
          align="start"
          sideOffset={4}
          onOpenAutoFocus={(event) => event.preventDefault()}
          onCloseAutoFocus={(event) => event.preventDefault()}
          onInteractOutside={(event) => {
            if (anchorRef.current?.contains(event.target as Node)) event.preventDefault();
          }}
          className="w-[var(--radix-popover-trigger-width)] rounded-xl bg-bg-white-0 p-1 shadow-regular-md ring-1 ring-inset ring-stroke-soft-200"
        >
          <ul id={listId} role="listbox" aria-label="Matching companies">
            {suggestions.map((company, index) => (
              <li
                key={company.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                // Keep focus in the input; a click picks on mousedown.
                onMouseDown={(event) => {
                  event.preventDefault();
                  pick(company);
                }}
                onMouseEnter={() => setActive(index)}
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5",
                  index === active && "bg-bg-weak-50",
                )}
              >
                <span className="flex size-4 shrink-0 items-center justify-center">
                  <CompanyFavicon domain={company.domain} className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-label-sm text-text-strong-950">{company.name || company.domain}</span>
                  <span className="block truncate text-paragraph-xs text-text-sub-600">{company.domain}</span>
                </span>
                {company.people > 0 && (
                  <span className="shrink-0 text-paragraph-xs text-text-soft-400">
                    {company.people} {company.people === 1 ? "person" : "people"}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Popover.Content>
      </Popover.Root>
    </div>
  );
}
