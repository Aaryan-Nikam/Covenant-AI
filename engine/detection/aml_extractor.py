import re
from dataclasses import dataclass

@dataclass
class AMLSignalCandidate:
    amount: float
    country_from: str | None
    pep_hit: bool
    raw_excerpt: str

class AMLExtractor:
    def __init__(self):
        # Match $10,000 or 10000 USD
        self.amount_pattern = re.compile(r'\$[\d,]+|\d+[\s]*(?:USD|dollars)', re.IGNORECASE)
        # High risk FATF
        self.fatf_countries = {
            "iran": "IR",
            "north korea": "KP",
            "myanmar": "MM",
            "syria": "SY",
            "yemen": "YE",
            "libya": "LY",
            "sudan": "SD"
        }
        # PEP terms
        self.pep_terms = [
            "politically exposed", "pep", "government official", 
            "minister", "senator", "sanctioned individual"
        ]

    def extract(self, content: str) -> AMLSignalCandidate | None:
        if not content:
            return None

        # Extract amount
        amounts_found = self.amount_pattern.findall(content)
        max_amount = 0.0
        for amt_str in amounts_found:
            clean_str = re.sub(r'[^\d.]', '', amt_str)
            try:
                val = float(clean_str)
                if val > max_amount:
                    max_amount = val
            except ValueError:
                continue

        if max_amount < 10000.0:
            return None

        content_lower = content.lower()
        
        # Check country
        country_hit = None
        for country, code in self.fatf_countries.items():
            if country in content_lower:
                country_hit = code
                break
                
        # Check PEP
        pep_hit = False
        for term in self.pep_terms:
            if term in content_lower:
                # To avoid false positive on just 'pep', check word boundary for 'pep'
                if term == "pep":
                    if re.search(r'\bpep\b', content_lower):
                        pep_hit = True
                        break
                else:
                    pep_hit = True
                    break

        if country_hit or pep_hit:
            return AMLSignalCandidate(
                amount=max_amount,
                country_from=country_hit,
                pep_hit=pep_hit,
                raw_excerpt=content
            )
            
        return None
