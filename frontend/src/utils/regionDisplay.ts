export function regionDisplayNameFor(countryQid: string | null | undefined): string {
  switch (countryQid) {
    case 'Q29':
    case 'Q29,Q45':
      return 'Iberia 868 AD'
    default:
      return countryQid ?? ''
  }
}
