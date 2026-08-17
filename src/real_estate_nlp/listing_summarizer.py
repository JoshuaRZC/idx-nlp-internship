import re

import nltk


class ListingSummarizer:
    """Build short, factual summaries from listing fields and extracted signals."""

    FEATURE_BUCKET_PRIORITY = (
        "amenities",
        "exterior_features",
        "interior_features",
        "location_features",
        "condition",
        "rooms",
        "parking",
        "property_type",
    )

    FEATURE_VALUE_PRIORITY = {
        "ocean view": 1,
        "ocean views": 1,
        "water view": 2,
        "panoramic views": 3,
        "mountain view": 4,
        "city lights view": 5,
        "pool": 6,
        "beach": 7,
        "solar": 8,
        "accessory dwelling unit": 9,
        "roof deck": 10,
        "covered patio": 11,
        "outdoor living": 12,
        "open floor plan": 13,
        "remodeled": 14,
        "new construction": 15,
        "fireplace": 16,
        "spa": 17,
    }

    BOILERPLATE_PATTERNS = (
        r"\bcall (?:listing )?agent\b",
        r"\bcontact (?:the )?(?:listing )?agent\b",
        r"\bdo not disturb\b",
        r"\bequal housing opportunity\b",
        r"\bsubject to (?:change|verification)\b",
        r"\b(?:www\.|https?://)\S+",
    )

    FIELD_ALIASES = {
        "beds": ("beds", "L_Keyword2"),
        "baths": ("baths", "LM_Dec_3"),
        "price": ("price", "L_SystemPrice"),
        "city": ("city", "L_City"),
        "remarks": ("remarks", "L_Remarks", "remarks_cleaned"),
    }

    def __init__(self, max_words=90):
        self.max_words = max_words

    def extractive_summary(self, remarks, entities=None, num_sentences=2):
        """Return the best source sentences while preserving their original order."""
        sentences = self._sentences(remarks)
        if not sentences:
            return ""

        entity_values = self._entity_values(entities)
        ranked = []
        for index, sentence in enumerate(sentences):
            score = 2 if index == 0 else 0
            score += self._feature_hits(sentence, entity_values)
            if self._is_boilerplate(sentence):
                score -= 3
            ranked.append((score, index, sentence))

        selected = sorted(ranked, key=lambda item: (-item[0], item[1]))[:num_sentences]
        return " ".join(sentence for _, _, sentence in sorted(selected, key=lambda item: item[1]))

    def summarize(self, listing_record, signals=None, num_sentences=2):
        """Return a compact hybrid summary for one complete listing record."""
        record = listing_record or {}
        details = {field: self._first_value(record, aliases) for field, aliases in self.FIELD_ALIASES.items()}
        sentences = [self._listing_sentence(details)]

        features = self._select_features((signals or {}).get("text_signals", {}), details["remarks"])
        if features:
            sentences.append(f"Highlights include {self._join_features(features)}.")
        else:
            extractive = self.extractive_summary(details["remarks"], num_sentences=1)
            if extractive:
                sentences.append(extractive)

        if num_sentences >= 3:
            extra = self._additional_sentence(details["remarks"], features, sentences)
            if extra:
                sentences.append(extra)

        return self._limit_words(sentences[:num_sentences])

    def _listing_sentence(self, details):
        beds = self._format_count(details["beds"])
        baths = self._format_count(details["baths"])
        city = self._text_value(details["city"])
        price = self._format_price(details["price"])

        descriptor = "listing"
        if beds and baths:
            descriptor = f"{beds}-bed, {baths}-bath listing"
        elif beds:
            descriptor = f"{beds}-bed listing"
        elif baths:
            descriptor = f"{baths}-bath listing"

        sentence = f"This {descriptor}"
        if city:
            sentence += f" in {city}"
        if price:
            sentence += f" is listed at {price}"
        elif city:
            sentence += " is located there"
        sentence += "."
        return sentence

    def _select_features(self, text_signals, remarks):
        candidates = []
        for bucket_index, bucket in enumerate(self.FEATURE_BUCKET_PRIORITY):
            for value in text_signals.get(bucket, []):
                value = self._text_value(value)
                if not value or re.fullmatch(r"\d+(?:\.0+)?", value):
                    continue
                candidates.append(
                    {
                        "bucket": bucket,
                        "value": value,
                        "bucket_index": bucket_index,
                        "value_priority": self.FEATURE_VALUE_PRIORITY.get(value, 100),
                        "position": self._feature_position(remarks, value),
                    }
                )

        candidates.sort(
            key=lambda item: (
                item["value_priority"],
                item["bucket_index"],
                item["position"],
                item["value"],
            )
        )

        selected = []
        used_buckets = set()
        for candidate in candidates:
            if candidate["bucket"] in used_buckets:
                continue
            selected.append(candidate["value"])
            used_buckets.add(candidate["bucket"])
            if len(selected) == 2:
                return selected

        for candidate in candidates:
            if candidate["value"] in selected:
                continue
            selected.append(candidate["value"])
            if len(selected) == 2:
                break
        return selected

    def _additional_sentence(self, remarks, features, existing_sentences):
        existing_text = " ".join(existing_sentences).lower()
        for sentence in self._sentences(remarks):
            if self._is_boilerplate(sentence) or sentence.lower() in existing_text:
                continue
            if any(feature in sentence.lower() for feature in features):
                continue
            return sentence
        return ""

    def _sentences(self, remarks):
        text = self._text_value(remarks)
        if not text:
            return []
        try:
            return [sentence.strip() for sentence in nltk.sent_tokenize(text) if sentence.strip()]
        except LookupError:
            return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]

    def _entity_values(self, entities):
        if not entities:
            return []
        if isinstance(entities, dict):
            values = entities.values()
        else:
            values = entities

        output = []
        for item in values:
            if isinstance(item, dict):
                value = item.get("value") or item.get("text")
                if value:
                    output.append(str(value).lower())
            elif isinstance(item, (list, tuple)):
                output.extend(self._entity_values(item))
            elif item is not None:
                output.append(str(item).lower())
        return output

    def _feature_hits(self, sentence, entity_values):
        text = sentence.lower()
        hits = 0
        for value in entity_values:
            if value and value in text:
                hits += 1
        return hits

    def _feature_position(self, remarks, feature):
        text = self._text_value(remarks).lower()
        variants = (feature, feature.replace("-", " "))
        positions = [text.find(variant) for variant in variants if text.find(variant) >= 0]
        return min(positions) if positions else len(text)

    def _join_features(self, features):
        phrases = [self._feature_phrase(feature) for feature in features]
        if len(phrases) == 1:
            return phrases[0]
        return f"{phrases[0]} and {phrases[1]}"

    def _feature_phrase(self, feature):
        phrases = {
            "beach": "beach access",
            "downtown": "a downtown location",
            "fenced": "fenced outdoor space",
            "freeway access": "freeway access",
            "move in ready": "move-in-ready condition",
            "near dining": "proximity to dining",
            "near shopping": "proximity to shopping",
            "public transportation": "public transportation access",
            "updated": "an updated interior",
            "remodeled": "a remodeled interior",
            "fixer upper": "fixer-upper condition",
            "new construction": "new construction",
            "view": "a view",
            "well maintained": "a well-maintained home",
        }
        if feature in phrases:
            return phrases[feature]
        if feature.startswith("near "):
            return feature
        if feature.startswith(("close to ", "near ")):
            return feature
        if feature in {"solar", "landscaping", "outdoor living", "waterfront", "parking"}:
            return feature
        if feature.endswith("flooring"):
            return feature
        if feature.endswith("s"):
            return feature
        if feature.startswith(("a ", "an ")):
            return feature
        article = "an" if feature[0] in "aeiou" else "a"
        return f"{article} {feature}"

    def _is_boilerplate(self, sentence):
        return any(re.search(pattern, sentence, flags=re.I) for pattern in self.BOILERPLATE_PATTERNS)

    def _limit_words(self, sentences):
        kept = []
        count = 0
        for sentence in sentences:
            words = sentence.split()
            if count + len(words) > self.max_words:
                break
            kept.append(sentence)
            count += len(words)
        return " ".join(kept)

    @staticmethod
    def _first_value(record, aliases):
        for alias in aliases:
            value = record.get(alias)
            if value is not None and str(value).strip() and str(value).lower() != "nan":
                return value
        return None

    @staticmethod
    def _text_value(value):
        if value is None or str(value).lower() == "nan":
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    @staticmethod
    def _format_count(value):
        if value is None:
            return ""
        number = float(value)
        if number <= 0:
            return ""
        return str(int(number)) if number.is_integer() else str(number)

    @staticmethod
    def _format_price(value):
        if value is None:
            return ""
        return f"${float(value):,.0f}"
