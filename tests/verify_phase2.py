"""Quick verification test for Phase 2 detection components."""
import sys
sys.path.insert(0, '.')

# Test 1: Luhn validator
from engine.detection.luhn_validator import LuhnValidator
luhn = LuhnValidator()

assert luhn.validate('4111111111111111') == True,  'Visa test card should pass'
assert luhn.validate('5500000000000004') == True,  'MC test card should pass'
assert luhn.validate('378282246310005') == True,   'Amex test card should pass'
assert luhn.validate('1234567890123456') == False, 'Random number should fail'
print('✅ Luhn validator: all tests passed')

# Test 2: Regex detector
from engine.detection.regex_detector import RegexDetector
from engine.detection.models import DetectorConfig

regex = RegexDetector()
content = 'My card is 4111111111111111 and SSN is 123-45-6789'

visa_det = DetectorConfig(
    id='visa', name='Visa', data_type='credit_card', layer=1,
    patterns=[r'\b4[0-9]{12}(?:[0-9]{3})?\b'],
    confidence_threshold=0.95,
)
ssn_det = DetectorConfig(
    id='ssn', name='SSN', data_type='ssn', layer=1,
    patterns=[r'\b(?!000|666)[0-9]{3}-(?!00)[0-9]{2}-(?!0000)[0-9]{4}\b'],
    confidence_threshold=0.99,
)

hits = regex.scan(content, [visa_det, ssn_det], 'test')
print(f'✅ Regex detector: found {len(hits)} hits')
for h in hits:
    print(f'   {h.detector_id}: "{h.value}" at position {h.position}')

assert hits[0].value == '4111111111111111'
assert hits[1].value == '123-45-6789'
print('✅ Regex positions: correct')

# Test 3: Luhn + Regex integration
validated = luhn.filter_detections(hits)
card_hits = [d for d in validated if d.data_type == 'credit_card']
assert len(card_hits) == 1
assert card_hits[0].layer == 2  # Upgraded from layer 1
print('✅ Luhn filter: card validated and upgraded to layer 2')

# Test 4: Ruleset loading
from engine.rulesets.loader import RulesetLoader
from engine.rulesets.registry import RulesetRegistry

loader = RulesetLoader()
rulesets = loader.load_all()
assert len(rulesets) == 4
print(f'✅ Rulesets: loaded {len(rulesets)} ({", ".join(rulesets.keys())})')

# Test 5: Registry
registry = RulesetRegistry()
registry.register_all(rulesets)
assert registry.is_registered('pci_dss')
assert registry.is_registered('hipaa')
merged = registry.get_merged_actions(['pci_dss', 'hipaa'])
assert 'credit_card' in merged
assert 'ssn' in merged
print(f'✅ Registry: merged actions from pci_dss + hipaa ({len(merged)} types)')

# Test 6: CVV always blocked
pci = registry.get('pci_dss')
cvv_action = pci.get_action_for_data_type('cvv')
assert cvv_action.primary == 'block', 'CVV must always be blocked'
print('✅ CVV enforcement: primary action is block')

print('\n🎉 All Phase 2 verification tests passed!')
