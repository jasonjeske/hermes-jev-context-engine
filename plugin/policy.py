"""Local egress exclusions, not a complete sensitive-data classifier.

Operator configuration declares approved scope. Transcript text never grants it.
Reject ambiguous injected context rather than strip delimiters and risk exporting it.
"""
import re

SCOPES = ('public_synthetic', 'personal_pilot')
PERSONAL_TOOLS = frozenset(('web_search',))
# Native memory_manager uses <memory-context>. Also refuse common profile/dump
# markers and unmatched opening/closing forms. This intentionally over-refuses.
EXCLUDED = re.compile(
    r'\bemployer\b|\bconfidential\b|\bproprietary\b|\bcompany[ _-]+internal\b|'
    r'\binternal[ _-]+only\b|\b(?:memory|user|soul)\.md\b|'
    r'\bmemory[ _-]+context\b|\buser[ _-]+profile\b|'
    r'\bpersistent[ _-]+memory\b|\b(?:memory|profile)[ _-]+dump\b|'
    r'<\s*/?\s*(?:memories|memory|profile)\b', re.I)


def scope_authorized(scope, employer_data_excluded=False, secrets_excluded=False):
    return scope in SCOPES and (scope != 'personal_pilot' or
        (employer_data_excluded is True and secrets_excluded is True))


def excluded_text(text):
    return bool(EXCLUDED.search(text))
