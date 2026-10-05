"use client";

/**
 * Een link in het hoofdmenu die weet waar de bezoeker is.
 *
 * Het menu staat in de layout, en die weet op de server niet welke pagina er
 * onder hangt — vandaar dit kleine client-onderdeel. Tot 5-10-2026 kwam
 * aria-current nergens op de site voor: een schermlezer hoorde zes gelijke
 * links en niet welke de huidige rubriek was, en ook op het scherm was dat
 * nergens aan te zien.
 *
 * Op de overzichtspagina zelf "page"; op een pagina eronder (een kantoor onder
 * Kantoren, een sector onder Sectoren) "true": de rubriek klopt, maar deze
 * link is niet de pagina zelf.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Menulink({
  href,
  ook = [],
  children,
}: {
  href: string;
  /** Adresvoorvoegsels die ook onder deze rubriek vallen, zoals "/kantoor". */
  ook?: string[];
  children: React.ReactNode;
}) {
  const pad = usePathname();
  const hier = pad === href;
  const eronder =
    !hier && [href, ...ook].some((voorvoegsel) => pad.startsWith(`${voorvoegsel}/`));
  return (
    <Link href={href} aria-current={hier ? "page" : eronder ? "true" : undefined}>
      {children}
    </Link>
  );
}
