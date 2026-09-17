export function splitName(fullName = '') {
  const parts = String(fullName).trim().split(/\s+/).filter(Boolean);
  return {
    firstName: parts[0] || '',
    lastName: parts.slice(1).join(' ') || ''
  };
}

export function normalizeLinkedInUrl(url = '') {
  const value = String(url || '').trim();
  if (!value) return '';
  if (value.startsWith('http')) return value.split('?')[0].replace(/\/$/, '');
  if (value.includes('linkedin.com/')) return `https://${value}`.split('?')[0].replace(/\/$/, '');
  return value;
}

export function parseNameFromLinkedInUrl(linkedinUrl = '') {
  const normalized = normalizeLinkedInUrl(linkedinUrl);
  const match = normalized.match(/linkedin\.com\/in\/([^/?#]+)/i);
  if (!match) return {};

  const cleanSlug = decodeURIComponent(match[1])
    .replace(/\d+/g, '')
    .replace(/[-_]+/g, ' ')
    .trim();

  return splitName(cleanSlug);
}

export function guessDomainFromCompany(company = '') {
  const clean = String(company || '')
    .toLowerCase()
    .replace(/\b(inc|llc|ltd|limited|pvt|private|corp|corporation|technologies|technology|solutions|services)\b/g, '')
    .replace(/[^a-z0-9]+/g, '')
    .trim();

  return clean ? `${clean}.com` : '';
}

export function normalizeCandidate(input = {}) {
  const fromFullName = splitName(input.fullName || input.name || '');
  const fromLinkedIn = parseNameFromLinkedInUrl(input.linkedinUrl || input.linkedin_url || '');
  const firstName = input.firstName || input.first_name || fromFullName.firstName || fromLinkedIn.firstName || '';
  const lastName = input.lastName || input.last_name || fromFullName.lastName || fromLinkedIn.lastName || '';
  const company = input.company || input.currentCompany || input.current_company || '';
  const domain = input.domain || guessDomainFromCompany(company);

  return {
    firstName: String(firstName).trim(),
    lastName: String(lastName).trim(),
    fullName: `${firstName || ''} ${lastName || ''}`.trim(),
    company: String(company).trim(),
    domain: String(domain).trim(),
    linkedinUrl: normalizeLinkedInUrl(input.linkedinUrl || input.linkedin_url || input.profileUrl || input.profile_url || '')
  };
}

export function lookupKey(candidate) {
  const normalized = normalizeCandidate(candidate);
  if (normalized.linkedinUrl) return `linkedin:${normalized.linkedinUrl.toLowerCase()}`;
  return [
    'person',
    normalized.firstName.toLowerCase(),
    normalized.lastName.toLowerCase(),
    normalized.company.toLowerCase(),
    normalized.domain.toLowerCase()
  ].join(':');
}

export function mapCsvRow(row = {}) {
  const get = (...keys) => {
    for (const key of keys) {
      const found = Object.keys(row).find(k => k.trim().toLowerCase() === key.toLowerCase());
      if (found && row[found]) return row[found];
    }
    return '';
  };

  return normalizeCandidate({
    firstName: get('first name', 'firstname', 'first'),
    lastName: get('last name', 'lastname', 'last'),
    fullName: get('name', 'full name', 'candidate name'),
    company: get('company', 'current company', 'employer', 'organization'),
    domain: get('domain', 'company domain', 'website'),
    linkedinUrl: get('linkedin url', 'linkedin', 'linkedin profile', 'profile url', 'profile')
  });
}
