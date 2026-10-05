"""Encode predicate symbols for LTLf parsing and retain reverse mappings."""

import re
from typing import List, Tuple, Dict


class SymbolNormalizer:
    """Convert predicate arguments and hyphens into propositional symbols."""

    HYPHEN_REPLACEMENT = "hh"
    HYPHEN_CHAR = "-"

    PREDICATE_PATTERN = re.compile(r'([a-z_][a-z0-9_]*)\(([^()]+)\)')

    def __init__(self):
        self.normalized_to_original: Dict[str, str] = {}
        self.original_to_normalized: Dict[str, str] = {}

    def encode_hyphens(self, text: str) -> str:
        """Replace hyphens with 'hh' and record the original spelling."""
        if self.HYPHEN_CHAR not in text:
            return text

        normalized = text.replace(self.HYPHEN_CHAR, self.HYPHEN_REPLACEMENT)

        if text not in self.original_to_normalized:
            self.original_to_normalized[text] = normalized
            self.normalized_to_original[normalized] = text

        return normalized

    def decode_hyphens(self, text: str) -> str:
        """Restore a recorded spelling, falling back to 'hh' replacement."""
        if self.HYPHEN_REPLACEMENT not in text:
            return text

        if text in self.normalized_to_original:
            return self.normalized_to_original[text]

        return text.replace(self.HYPHEN_REPLACEMENT, self.HYPHEN_CHAR)

    def normalize_predicate_args(self, predicate: str, args: List[str]) -> Tuple[str, List[str]]:
        """Encode hyphens in a predicate name and its arguments."""
        normalized_predicate = self.encode_hyphens(predicate)
        normalized_args = [self.encode_hyphens(arg) for arg in args]

        return normalized_predicate, normalized_args

    def create_propositional_symbol(self, predicate: str, args: List[str]) -> str:
        """Encode on(a, b) as on_a_b and retain its reverse mapping."""
        norm_pred, norm_args = self.normalize_predicate_args(predicate, args)

        if not norm_args:
            return norm_pred.lower()

        symbol = f"{norm_pred.lower()}_{'_'.join(arg.lower() for arg in norm_args)}"

        # Store reverse mapping for the entire symbol
        original_symbol = self._create_original_symbol(predicate, args)
        self.normalized_to_original[symbol] = original_symbol
        self.original_to_normalized[original_symbol] = symbol

        return symbol

    def _create_original_symbol(self, predicate: str, args: List[str]) -> str:
        """Create original symbol (with hyphens) for reverse mapping"""
        if not args:
            return predicate.lower()
        return f"{predicate.lower()}_{'_'.join(arg.lower() for arg in args)}"

    def restore_symbol_hyphens(self, normalized_symbol: str) -> str:
        """Restore the original hyphenated propositional symbol."""
        if normalized_symbol in self.normalized_to_original:
            return self.normalized_to_original[normalized_symbol]

        return self.decode_hyphens(normalized_symbol)
