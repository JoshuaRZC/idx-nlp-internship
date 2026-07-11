import json
import re
from pathlib import Path


class EntityExtractor:
    NUMBER_WORDS = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "single": 1,
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
    }
    NUMBER_PATTERN = r"(?:\d{1,3}(?:,\s*\d{3})+|\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|single|first|second|third|fourth|fifth|sixth)"
    COUNT_NUMBER_PATTERN = r"(?:\d{1,2}(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|single)"

    METHOD_PRIORITY = {
        "regex": 1,
        "taxonomy": 2,
        "ner": 3,
    }

    LABEL_PRIORITY = {
        "price": 1,
        "hoa_fee": 1,
        "year_built": 1,
        "sqft": 2,
        "lot_size": 2,
        "bedrooms": 2,
        "bathrooms": 2,
        "parking": 2,
        "stories": 2,
        "property_type": 3,
        "transaction_or_listing": 3,
        "condition": 3,
        "location": 3,
        "room": 3,
        "amenity": 3,
        "interior_feature": 3,
        "exterior_feature": 3,
    }

    BLOCKED_TAXONOMY_MATCHES = {
        ("condition", "beautifully remodeled", "beautifully remodeled"),
        ("condition", "beautifully updated", "beautifully updated"),
        ("condition", "brand new", "brand new"),
        ("condition", "fully remodeled", "fully remodeled"),
        ("condition", "modern", "modern"),
        ("condition", "modern", "modern living"),
        ("condition", "modern comfort", "modern comfort"),
        ("condition", "modern design", "modern design"),
        ("condition", "modern luxury", "modern luxury"),
        ("condition", "move-in ready home", "move in ready home"),
        ("condition", "upgraded", "upgraded"),
        ("exterior_feature", "patio", "patio"),
        ("exterior_feature", "back patio", "back patio"),
        ("exterior_feature", "ample parking", "ample parking"),
        ("exterior_feature", "paid solar panels", "paid solar panels"),
        ("exterior_feature", "parking", "parking"),
        ("exterior_feature", "parking spaces", "parking spaces"),
        ("exterior_feature", "private backyard", "private backyard"),
        ("exterior_feature", "private balcony", "private balcony"),
        ("exterior_feature", "private patio", "private patio"),
        ("interior_feature", "cozy fireplace", "cozy fireplace"),
        ("interior_feature", "custom cabinetry", "custom cabinetry"),
        ("interior_feature", "abundant natural light", "abundant natural light"),
        ("interior_feature", "abundance of natural light", "abundance of natural light"),
        ("interior_feature", "flooring", "flooring"),
        ("interior_feature", "floor plan", "layout"),
        ("interior_feature", "soaring ceilings", "soaring ceilings"),
        ("interior_feature", "thoughtfully designed floor plan", "thoughtfully designed floor plan"),
        ("interior_feature", "windows", "windows"),
        ("location", "direct access", "direct access"),
        ("location", "easy access", "easy access"),
        ("location", "neighborhood", "neighborhood"),
        ("location", "close to shopping", "close to shopping"),
        ("location", "near shopping", "near shopping"),
        ("location", "shopping restaurants", "shopping, dining"),
        ("location", "shopping restaurants", "shopping restaurants"),
        ("location", "sweeping views", "sweeping views"),
        ("amenity", "golf course", "golf"),
        ("amenity", "sparkling pool", "sparkling pool"),
        ("room", "bathroom", "bathroom"),
        ("room", "bedroom", "bedroom"),
        ("room", "generously sized bedrooms", "generously sized bedrooms"),
        ("room", "multi-generational living", "multi generational living"),
        ("room", "spacious kitchen", "spacious kitchen"),
        ("room", "updated kitchen", "updated kitchen"),
    }

    PHRASE_ENTITIES = [
        ("new windows", "condition", "new windows"),
        ("updated kitchen", "condition", "updated kitchen"),
        ("updated bathroom", "condition", "updated bathroom"),
        ("updated bathrooms", "condition", "updated bathroom"),
        ("upgraded kitchen", "condition", "upgraded"),
        ("upgraded flooring", "condition", "upgraded flooring"),
        ("new tile", "condition", "new tile"),
        ("new construction", "condition", "new construction"),
        ("brand new construction", "condition", "brand new"),
        ("newer windows", "condition", "newer windows"),
        ("unfinished construction", "condition", "unfinished construction"),
        ("custom built", "condition", "custom built"),
        ("meticulously maintained", "condition", "well maintained"),
        ("newly painted", "condition", "new paint"),
        ("newer interior exterior paint", "condition", "new paint"),
        ("fresh interior and exterior paint", "condition", "fresh paint"),
        ("brand new carpet", "condition", "new carpet"),
        ("interior paint", "condition", "freshly painted"),
        ("remodeled kitchen", "condition", "remodeled"),
        ("complete remodel", "condition", "remodeled"),
        ("newly remodeled bathroom", "condition", "remodeled"),
        ("bathroom have been remodeled", "condition", "remodeled"),
        ("newly constructed", "condition", "new construction"),
        ("newly refurbished", "condition", "refurbished"),
        ("fresh finishes", "condition", "fresh finishes"),
        ("renovate", "condition", "renovation"),
        ("renovation project", "condition", "renovation project"),
        ("recently updated", "condition", "updated"),
        ("updated throughout", "condition", "updated"),
        ("fully updated", "condition", "updated"),
        ("updated bath", "condition", "updated bathroom"),
        ("upgrades", "condition", "upgrades"),
        ("future upgrades", "condition", "upgrades"),
        ("several upgrades", "condition", "upgrades"),
        ("modern upgrades", "condition", "upgrades"),
        ("premium upgrades", "condition", "upgrades"),
        ("needed some tlc", "condition", "tlc"),

        ("spacious kitchen", "room", "kitchen"),
        ("kitchens", "room", "kitchen"),
        ("secondary kitchen area", "room", "kitchen"),
        ("eat in kitchen", "room", "eat-in kitchen"),
        ("newer kitchen", "room", "kitchen"),
        ("open kitchen", "room", "open kitchen"),
        ("breakfast bar", "room", "breakfast bar"),
        ("primary suite", "room", "primary suite"),
        ("primary suites", "room", "primary suite"),
        ("owner's suite", "room", "primary suite"),
        ("secondary bedrooms", "room", "secondary bedroom"),
        ("large closet", "room", "closet space"),
        ("large master", "room", "master bedroom"),
        ("art studio", "room", "studio"),
        ("office studio", "room", "studio"),
        ("main residence", "room", "main residence"),
        ("pantry", "room", "pantry"),
        ("walk in pantry", "room", "walk-in pantry"),
        ("indoor laundry room", "room", "indoor laundry"),
        ("inside laundry room", "room", "indoor laundry"),
        ("inside laundry", "room", "indoor laundry"),
        ("in unit laundry", "room", "laundry room"),
        ("inside laundry room", "room", "indoor laundry"),
        ("laundry area", "room", "laundry room"),
        ("in garage laundry", "room", "laundry room"),
        ("laundry hookups", "room", "laundry room"),
        ("in home laundry", "room", "laundry room"),
        ("ensuite bathroom", "room", "en suite bathroom"),
        ("en suite bathroom", "room", "en suite bathroom"),
        ("en suite bath", "room", "en suite bathroom"),
        ("ensuite bath", "room", "en suite bathroom"),
        ("on suite bath", "room", "en suite"),
        ("formal dinning room", "room", "formal dining room"),
        ("dinning room", "room", "dining room"),
        ("dining space", "room", "dining area"),

        ("washer and dryer", "interior_feature", "washer dryer"),
        ("washer dryer", "interior_feature", "washer dryer"),
        ("open concept", "interior_feature", "open concept"),
        ("open concept floorplan", "interior_feature", "open floor plan"),
        ("open concept floor plan", "interior_feature", "open floor plan"),
        ("open floorplan", "interior_feature", "open floor plan"),
        ("open, airy floor plan", "interior_feature", "open floor plan"),
        ("functional floorplan", "interior_feature", "floor plan"),
        ("central air conditioning", "interior_feature", "central air conditioning"),
        ("central air", "interior_feature", "central air conditioning"),
        ("heating ventilation and air conditioning", "interior_feature", "air conditioning"),
        ("central heating ventilation and air conditioning", "interior_feature", "central air conditioning"),
        ("natural sunlight", "interior_feature", "natural light"),
        ("stone fireplace", "interior_feature", "fireplace"),
        ("gas burning fireplace", "interior_feature", "fireplace"),
        ("brick fireplace", "interior_feature", "fireplace"),
        ("wood burning fireplace", "interior_feature", "fireplace"),
        ("gas starter fireplace", "interior_feature", "fireplace"),
        ("gas fireplace", "interior_feature", "fireplace"),
        ("tile floor", "interior_feature", "tile flooring"),
        ("luxury vinyl plank flooring", "interior_feature", "luxury vinyl plank"),
        ("laminate wood plank flooring", "interior_feature", "laminate flooring"),
        ("hardwood floors", "interior_feature", "hardwood floors"),
        ("walk in closets", "interior_feature", "walk-in closet"),
        ("caesarstone countertops", "interior_feature", "quartz countertops"),
        ("sliding doors", "interior_feature", "sliding glass doors"),
        ("designer cabinetry", "interior_feature", "cabinetry"),
        ("white shaker cabinets", "interior_feature", "cabinetry"),
        ("ample cabinetry", "interior_feature", "cabinetry"),
        ("convenient island", "interior_feature", "center island"),
        ("new dishwasher", "interior_feature", "dishwasher"),
        ("electric appliances", "interior_feature", "appliances"),
        ("led recessed lighting", "interior_feature", "recessed lighting"),
        ("ceiling fans", "interior_feature", "ceiling fan"),
        ("high vaulted ceilings", "interior_feature", "vaulted ceilings"),
        ("subway tile backsplash", "interior_feature", "tile backsplash"),

        ("private deck", "exterior_feature", "deck"),
        ("covered deck", "exterior_feature", "deck"),
        ("private patio", "exterior_feature", "patio"),
        ("back patio", "exterior_feature", "patio"),
        ("rooftop patio", "exterior_feature", "patio"),
        ("enclosed patio", "exterior_feature", "patio"),
        ("mini patios", "exterior_feature", "patio"),
        ("enclosed front patio", "exterior_feature", "patio"),
        ("attached patio cover", "exterior_feature", "patio"),
        ("brick patio", "exterior_feature", "patio"),
        ("covered backyard patio", "exterior_feature", "patio"),
        ("community patio", "exterior_feature", "patio"),
        ("open patio", "exterior_feature", "patio"),
        ("private ocean view patio", "exterior_feature", "patio"),
        ("patio space", "exterior_feature", "patio"),
        ("rear patio", "exterior_feature", "patio"),
        ("cover patio", "exterior_feature", "covered patio"),
        ("fenced patio", "exterior_feature", "patio"),
        ("front and back yard", "exterior_feature", "yard"),
        ("chain link fence", "exterior_feature", "fence"),
        ("fully fenced", "exterior_feature", "fenced"),
        ("fenced pastures", "exterior_feature", "fenced"),
        ("mature landscaping", "exterior_feature", "landscaping"),
        ("solar system", "exterior_feature", "solar"),
        ("leased solar", "exterior_feature", "solar"),
        ("solar energy panels", "exterior_feature", "solar"),
        ("solar panels", "exterior_feature", "solar"),
        ("paid solar", "exterior_feature", "solar"),
        ("paid solar panels", "exterior_feature", "solar"),
        ("fully paid solar panels", "exterior_feature", "solar"),
        ("fully paid solar", "exterior_feature", "solar"),
        ("12 owned solar panels", "exterior_feature", "solar"),
        ("landscaped backyard", "exterior_feature", "backyard"),
        ("spacious yard", "exterior_feature", "yard"),
        ("private yard", "exterior_feature", "yard"),
        ("outdoor oasis", "exterior_feature", "outdoor living"),
        ("outdoor entertainment", "exterior_feature", "outdoor living"),
        ("outdoor space", "exterior_feature", "outdoor living"),
        ("private outdoor terraces", "exterior_feature", "outdoor terrace"),
        ("terraces", "exterior_feature", "terrace"),

        ("pools", "amenity", "pool"),
        ("swimming pools", "amenity", "swimming pool"),
        ("inground pool", "amenity", "pool"),
        ("inground swimming pool", "amenity", "pool"),
        ("private in ground pool", "amenity", "pool"),
        ("sparkling pool", "amenity", "pool"),
        ("pool and spa", "amenity", "pool and spa"),
        ("jacuzzi", "amenity", "hot tub"),
        ("outdoor jacuzzi", "amenity", "hot tub"),
        ("jacuzzi spas", "amenity", "hot tub"),
        ("two golf courses", "amenity", "golf course"),
        ("golf courses", "amenity", "golf course"),
        ("tennis courts", "amenity", "tennis courts"),
        ("resort amenities", "amenity", "resort amenities"),
        ("equestrian amenities", "amenity", "equestrian amenities"),

        ("quiet street", "location", "quiet neighborhood"),
        ("quiet and nice street", "location", "quiet neighborhood"),
        ("close to downtown", "location", "close to downtown"),
        ("transit", "location", "transit"),
        ("school district", "location", "school district"),
        ("golf club", "location", "golf course"),
        ("riverfront home", "location", "riverfront"),
        ("breathtaking views", "location", "views"),
        ("water views", "location", "water view"),
        ("white water views", "location", "water view"),
        ("hillside view", "location", "view"),
        ("sunset views", "location", "views"),
        ("west facing views", "location", "views"),
        ("westward views", "location", "views"),
        ("close to the freeway", "location", "close to freeway"),
        ("easy access to the 101 freeway", "location", "freeway access"),
        ("close to award winning schools", "location", "close to schools"),
        ("top schools", "location", "top-rated schools"),
        ("top rated newport mesa schools", "location", "top-rated schools"),
        ("shopping, restaurants", "location", "shopping restaurants"),

        ("street parking", "parking", "street parking"),
        ("off street parking", "parking", "off street parking"),
        ("driveway parking", "parking", "driveway parking"),
        ("guest parking", "parking", "guest parking"),
        ("parking space", "parking", "parking space"),
        ("plenty of parking", "parking", "parking"),
        ("open parking", "parking", "parking"),
        ("on site parking", "parking", "parking"),
        ("parking behind the back patio", "parking", "parking"),
        ("assigned spot", "parking", "assigned parking"),
        ("2 car parking space", "parking", 2),
        ("two underground parking spaces", "parking", 2),
        ("attached 2 cars garage", "parking", 2),
        ("1 car garages", "parking", 1),
        ("secure garage parking", "parking", "garage parking"),
        ("underground parking garage", "parking", "underground parking garage"),

        ("va approved", "transaction_or_listing", "va loan"),
        ("va financing", "transaction_or_listing", "va loan"),
        ("as is", "transaction_or_listing", "as is"),
        ("lease contract", "transaction_or_listing", "lease"),
        ("for lease", "transaction_or_listing", "lease"),
        ("investment opportunity", "transaction_or_listing", "investment"),
        ("rental opportunity", "transaction_or_listing", "rental"),
        ("great rental", "transaction_or_listing", "rental"),
        ("tenant occupied", "transaction_or_listing", "tenant occupied"),
        ("55 age restricted community", "transaction_or_listing", "55 community"),
        ("55 community", "transaction_or_listing", "55 community"),
    ]

    def __init__(self, taxonomy_path="data/processed/taxonomy.json", ner_model=None):
        self.taxonomy_path = Path(taxonomy_path)
        if not self.taxonomy_path.exists() and not self.taxonomy_path.is_absolute():
            self.taxonomy_path = Path(__file__).resolve().parents[1] / self.taxonomy_path
        self.ner_model = ner_model
        self.taxonomy_terms = self._load_taxonomy_terms(self.taxonomy_path)

    def extract_all(self, text):
        text = "" if text is None else str(text)

        entities = []
        entities.extend(self.extract_regex_entities(text))
        entities.extend(self.extract_phrase_entities(text))
        entities.extend(self.extract_taxonomy_terms(text))
        entities.extend(self.extract_ner_entities(text))

        entities = self._deduplicate_entities(entities)
        return self._resolve_conflicts(entities)

    def extract_regex_entities(self, text):
        entities = []
        entities.extend(self.extract_bedrooms(text))
        entities.extend(self.extract_bathrooms(text))
        entities.extend(self.extract_price(text))
        entities.extend(self.extract_sqft(text))
        entities.extend(self.extract_lot_size(text))
        entities.extend(self.extract_year_built(text))
        entities.extend(self.extract_stories(text))
        entities.extend(self.extract_parking(text))
        entities.extend(self.extract_hoa(text))
        return entities

    def extract_phrase_entities(self, text):
        entities = []
        for phrase, label, value in self.PHRASE_ENTITIES:
            for match in self._term_pattern(phrase).finditer(text):
                entities.append(
                    {
                        "label": label,
                        "value": value,
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "method": "regex",
                        "source": "phrase_rule",
                    }
                )
        return entities

    def extract_bedrooms(self, text):
        patterns = [
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s*(?:bedroom|bedrooms|bed|beds|br|bd)\b", "bedroom_count"),
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s+(?:spacious|additional|guest|secondary)\s+(?:bed\s*rooms?|bedrooms|bedroom|beds?)\b", "described_bedroom_count"),
        ]
        return self._extract_number_patterns(text, "bedrooms", patterns, max_value=20)

    def extract_bathrooms(self, text):
        entities = []
        patterns = [
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s*(?:n?bathroom|n?bathrooms|n?bath|n?baths|ba|bth)\b", "bathroom_count"),
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s+full\s+(?:bathroom|bath)\b", "full_bathroom_count"),
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s+half\s+(?:bathroom|bath)\b", "half_bathroom_count"),
            (r"\bhalf\s+(?:bathroom|bath)\b", "half_bathroom"),
            (r"\bfull\s+(?:bathroom|bath)\b", "full_bathroom"),
            (r"\b(\d)1\s*2\s*(?:bathroom|bath)\b", "half_fraction_bathroom"),
        ]
        for pattern, source in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                if source == "half_bathroom":
                    value = 0.5
                elif source == "full_bathroom":
                    value = 1
                elif source == "half_fraction_bathroom":
                    value = int(match.group(1)) + 0.5
                else:
                    value = self._to_number(match.group(1))
                if value > 20:
                    continue
                entities.append(self._entity("bathrooms", value, match, source))
        return entities

    def extract_price(self, text):
        patterns = [
            (r"\b(?:listed|priced|asking|offered)\s+(?:at|for)?\s*(\d{5,8})\b", "listing_price"),
            (r"\b(?:price|asking price|list price)\s*(?:is|at)?\s*(\d{5,8})\b", "listing_price"),
        ]
        entities = []
        for pattern, source in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                value = int(match.group(1))
                if 50_000 <= value <= 100_000_000:
                    entities.append(self._entity("price", value, match, source))
        return self._resolve_conflicts(entities)

    def extract_sqft(self, text):
        pattern = (
            r"(?<!\w)(?:(?:approximately|approx\.?|about|around|over)\s+)?"
            r"(\d{1,3}(?:,\s*\d{3})+|\d{3,6}(?:\.\d+)?)"
            r"\s*(?:square feet|square foot|sqft|sq ft|sq|sf)\b"
            r"(?!\s*(?:lot|parcel|site|corner\s+lot))"
        )
        entities = []
        for match in re.finditer(pattern, text, flags=re.I):
            entities.append(
                self._entity_from_span(
                    "sqft",
                    self._to_number(match.group(1)),
                    text,
                    match.start(1),
                    match.end(),
                    "living_area",
                )
            )
        return entities

    def extract_lot_size(self, text):
        entities = []
        patterns = [
            (r"(?<!\w)(?:(?:approximately|approx\.?|about|around|over|almost)\s+)?(\d+(?:\.\d+)?)\s*acres?(?:\s+(?:lot|parcel|site))?\b", "acre_lot"),
            (r"\blot size is\s+(\d{1,3}(?:,\s*\d{3})+|\d{3,7}(?:\.\d+)?)\s*(?:square feet|square foot|sq\.?\s*feet|sqft|sq ft|sq|sf)\b", "sqft_lot"),
            (r"\blot size of\s+(?:(?:approximately|approx\.?|about|around|over)\s+)?(\d{1,3}(?:,\s*\d{3})+|\d{3,7}(?:\.\d+)?)\s*(?:square feet|square foot|sq\.?\s*feet|sqft|sq ft|sq|sf)\b", "sqft_lot"),
            (r"(?<!\w)(\d{1,3}(?:,\s*\d{3})+|\d{3,7}(?:\.\d+)?)\s*(?:square feet|square foot|sq\.?\s*feet|sqft|sq ft|sq|sf)\s+corner\s+lot\b", "sqft_lot"),
            (r"(?<!\w)(?:(?:approximately|approx\.?|about|around|over)\s+)?(\d{1,3}(?:,\s*\d{3})+|\d{3,7}(?:\.\d+)?)\s*(?:square feet|square foot|sq\.?\s*feet|sqft|sq ft|sq|sf)\s*(?:lot|parcel|site)\b", "sqft_lot"),
            (r"\b(\d+(?:\.\d+)?)\s+by\s+(\d+(?:\.\d+)?)\s+foot\s+lot\b", "lot_dimensions"),
            (r"\bjust under half an acre\b", "half_acre_lot"),
        ]

        for pattern, source in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                if source == "lot_dimensions":
                    value = {
                        "width_ft": float(match.group(1)),
                        "depth_ft": float(match.group(2)),
                    }
                elif source == "half_acre_lot":
                    value = 0.5
                else:
                    value = self._to_number(match.group(1))
                if source == "sqft_lot":
                    entities.append(
                        self._entity_from_span(
                            "lot_size",
                            value,
                            text,
                            match.start(1),
                            match.end(),
                            source,
                        )
                    )
                else:
                    entities.append(self._entity("lot_size", value, match, source))
        return entities

    def extract_year_built(self, text):
        patterns = [
            (r"\byear built\s+((?:18|19|20)\d{2})\b", "year_built"),
            (r"\bbuilt\s+in\s+((?:18|19|20)\d{2})\b", "built_in_year"),
        ]
        return self._extract_number_patterns(text, "year_built", patterns, cast=int)

    def extract_stories(self, text):
        entities = []
        patterns = [
            (rf"\b({self.NUMBER_PATTERN})\s*(?:story|stories)\b", "story_count"),
            (r"\bsplit level\b", "split_level"),
        ]
        for pattern, source in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                value = "split level" if source == "split_level" else self._to_number(match.group(1))
                entities.append(self._entity("stories", value, match, source))
        return entities

    def extract_parking(self, text):
        entities = []
        patterns = [
            (rf"\battached\s+({self.COUNT_NUMBER_PATTERN})\s+car\s+garage\b", "attached_garage_count"),
            (rf"\bdetached\s+({self.COUNT_NUMBER_PATTERN})\s+car\s+garage\b", "detached_garage_count"),
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s+car\s+(?:attached\s+|detached\s+|oversized\s+)?garage\b", "garage_count"),
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s+car\s+direct\s+access\b", "direct_access_parking_count"),
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s+car\s+parking\b", "parking_count"),
            (rf"\bparking\s+space\s+for\s+({self.COUNT_NUMBER_PATTERN})\s+cars?\b", "parking_count"),
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s+(?:assigned|covered|deeded|reserved|tandem)?\s*parking\b", "parking_count"),
            (rf"\b({self.COUNT_NUMBER_PATTERN})\s+(?:assigned|covered|deeded|reserved|tandem)?\s*parking\s+spaces?\b", "parking_count"),
        ]
        entities.extend(self._extract_number_patterns(text, "parking", patterns, max_value=12))

        for match in re.finditer(r"\b(?:attached|detached)\s+garage\b|\bgarage\b|\bcarport\b", text, flags=re.I):
            entities.append(self._entity("parking", match.group(0).lower(), match, "parking_feature"))
        return entities

    def extract_hoa(self, text):
        entities = []
        for match in re.finditer(
            r"\bhomeowners association fee(?:s| dues)?(?:\s+of)?\s+(\d+(?:,\s*\d{3})*(?:\.\d+)?)\s*(?:per month|monthly)?\b",
            text,
            flags=re.I,
        ):
            entities.append(self._entity("hoa_fee", self._to_number(match.group(1)), match, "monthly_hoa_fee"))

        for match in re.finditer(r"\bno homeowners association\b", text, flags=re.I):
            entities.append(self._entity("hoa_fee", 0, match, "no_hoa"))
        return entities

    def extract_taxonomy_terms(self, text):
        entities = []
        for item in self.taxonomy_terms:
            for match in item["pattern"].finditer(text):
                matched_text = match.group(0).lower()
                if self._skip_taxonomy_match(item["category"], item["term"], matched_text, text, match):
                    continue
                entities.append(
                    {
                        "label": item["category"],
                        "value": item["term"],
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "method": "taxonomy",
                        "source": item["id"],
                    }
                )
        return entities

    def _skip_taxonomy_match(self, label, value, matched_text, full_text, match):
        if (label, value, matched_text) in self.BLOCKED_TAXONOMY_MATCHES:
            return True

        tail = full_text[match.end(): match.end() + 20].lower()
        if label == "location" and value == "dining" and re.match(r"\s+(?:room|area|space)\b", tail):
            return True

        head = full_text[max(0, match.start() - 25): match.start()].lower()
        if label == "room" and value in {"bedroom", "bathroom"}:
            if matched_text in {"bedrooms", "bathrooms"}:
                return True
            if re.search(rf"(?:{self.COUNT_NUMBER_PATTERN})\s+$", head):
                return True

        return False

    def extract_ner_entities(self, text):
        if self.ner_model is None:
            return []

        if hasattr(self.ner_model, "extract"):
            entities = self.ner_model.extract(text)
        elif callable(self.ner_model):
            entities = self.ner_model(text)
        else:
            raise TypeError("ner_model must be callable or expose an extract(text) method")

        normalized = []
        for entity in entities:
            item = dict(entity)
            item.setdefault("method", "ner")
            item.setdefault("source", self.ner_model.__class__.__name__)
            normalized.append(item)
        return normalized

    def _extract_number_patterns(self, text, label, patterns, cast=None, max_value=None):
        entities = []
        for pattern, source in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                value = match.group(1)
                value = cast(value) if cast else self._to_number(value)
                if max_value is not None and value > max_value:
                    continue
                entities.append(self._entity(label, value, match, source))
        return entities

    def _entity(self, label, value, match, source):
        return {
            "label": label,
            "value": value,
            "text": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "method": "regex",
            "source": source,
        }

    def _entity_from_span(self, label, value, text, start, end, source):
        return {
            "label": label,
            "value": value,
            "text": text[start:end],
            "start": start,
            "end": end,
            "method": "regex",
            "source": source,
        }

    def _load_taxonomy_terms(self, taxonomy_path):
        if not taxonomy_path.exists():
            return []

        with taxonomy_path.open() as f:
            taxonomy = json.load(f)

        terms = []
        aliases = self._taxonomy_aliases()
        for item in taxonomy.get("terms", []):
            names = [item["term"], *item.get("aliases", []), *aliases.get(item["term"], [])]
            for name in names:
                pattern = self._term_pattern(name)
                terms.append(
                    {
                        "id": item["id"],
                        "term": item["term"],
                        "category": item["category"],
                        "pattern": pattern,
                    }
                )

        for item in self._supplemental_taxonomy_terms():
            names = [item["term"], *item.get("aliases", [])]
            for name in names:
                terms.append(
                    {
                        "id": item["id"],
                        "term": item["term"],
                        "category": item["category"],
                        "pattern": self._term_pattern(name),
                    }
                )

        return sorted(terms, key=lambda item: len(item["term"]), reverse=True)

    def _taxonomy_aliases(self):
        return {
            "move-in ready": ["move in ready", "ready for move in"],
            "turnkey": ["turn key"],
            "updated": ["completely updated", "beautiful updated", "beautifully updated"],
            "remodeled": ["completely remodeled", "fully remodeled", "beautifully remodeled", "recently remodeled"],
            "renovated": ["beautifully renovated", "recently renovated", "renovate"],
            "freshly painted": ["recently painted", "fresh interior and exterior paint", "fresh interior paint"],
            "new flooring": ["brand new wood flooring", "new high quality vinyl flooring", "new luxury vinyl flooring"],
            "new roof": ["brand new roof", "roof replaced"],
            "new windows": ["brand new windows"],
            "new carpet": ["new carpeting"],
            "brand new": ["brand new construction"],

            "pool": ["in ground pool", "inground pool", "private pool", "sparkling pool"],
            "spa": ["jacuzzi"],
            "hot tub": ["outdoor jacuzzi"],
            "pool and spa": ["pool and spa"],
            "bbq area": ["bbq pavilion"],

            "walk-in closet": ["walk in closet", "walking closet"],
            "quartz countertops": ["quartz counter tops", "quartz counters", "quartz countertop"],
            "granite countertops": ["granite counter tops", "granite counters"],
            "stainless steel appliances": ["stainless appliances"],
            "dual-pane windows": ["dual pane windows", "double pane windows", "duel pane windows"],
            "central air conditioning": ["central air", "central heat air conditioning", "central refrigerated air"],
            "air conditioning": ["heating ventilation and air conditioning"],
            "open floor plan": ["open concept floor plan", "open concept floorplan", "open layout", "open and airy layout"],
            "open concept": ["open concept"],
            "floor plan": ["floorplan", "functional layout"],
            "sliding glass doors": ["sliding glass door"],
            "washer dryer": ["washer and dryer", "washer dryer"],
            "center island": ["large island", "large center island"],
            "high ceilings": ["soaring ceilings"],
            "cabinetry": ["cabinets", "custom cabinetry"],
            "roof deck": ["roof top deck", "rooftop entertainment deck"],
            "covered patio": ["covered back patio", "attached patio cover"],
            "rv parking": ["rv access", "gated rv access"],
            "driveway": ["long driveway"],

            "freeway access": ["access to the 215 freeway", "access to the 710 freeway", "easy access to highways"],
            "close to schools": ["close proximity to schools"],
            "close to shopping": ["close to shopping"],
            "near schools": ["nearby schools", "near to local schools"],
            "walking distance": ["short walking distance"],
            "mountain views": ["mountain scenery", "mountain and treetop views"],
            "ocean view": ["ocean views", "ocean and mountain view"],
            "city view": ["view of the city"],
            "gated community": ["secure gated community"],
            "patio": ["fenced patio"],
            "backyard": ["back yard"],
            "balcony": ["private balcony"],
            "deck": ["private deck"],
            "outdoor living": ["outdoor space"],
            "vaulted ceilings": ["vaulted ceiling"],
            "townhome": ["townho"],

            "rental income": ["live in one and rent the out the other", "rent the out the other", "income producing property"],
            "investment": ["investor", "investors", "investor's delight", "investor's opportunity"],
            "price reduction": ["priced to sell", "price improvement"],
            "cash offer": ["cash offers"],
            "seller financing": ["owner financing"],
            "as is": ["sold as is"],
            "fixer upper": ["major fixer upper", "true fixer upper"],
            "hoa": ["homeowners association", "homeowners association dues"],
            "low hoa": ["low homeowners association", "low homeowners association dues"],
            "commercial property": ["commercial and residential use"],
            "shopping restaurants": ["shopping and restaurants", "restaurants, shopping", "shopping, dining"],
            "schools": ["great schools"],
            "elementary school": ["elementary"],
        }

    def _supplemental_taxonomy_terms(self):
        return [
            {"id": "supplemental_property_type_001", "term": "accessory dwelling unit", "category": "property_type", "aliases": []},
            {"id": "supplemental_property_type_002", "term": "detached condo", "category": "property_type", "aliases": []},
            {"id": "supplemental_property_type_003", "term": "stock cooperative", "category": "transaction_or_listing", "aliases": []},

            {"id": "supplemental_condition_001", "term": "fresh paint", "category": "condition", "aliases": ["fresh coat of paint"]},
            {"id": "supplemental_condition_002", "term": "excellent condition", "category": "condition", "aliases": ["excellent conditions"]},
            {"id": "supplemental_condition_003", "term": "new kitchen", "category": "condition", "aliases": ["brand new kitchen"]},
            {"id": "supplemental_condition_004", "term": "new cabinetry", "category": "condition", "aliases": []},
            {"id": "supplemental_condition_005", "term": "new water heater", "category": "condition", "aliases": []},
            {"id": "supplemental_condition_006", "term": "ready to build", "category": "condition", "aliases": ["ready to build lot"]},
            {"id": "supplemental_condition_007", "term": "new paint", "category": "condition", "aliases": []},
            {"id": "supplemental_condition_008", "term": "tlc", "category": "condition", "aliases": ["some tlc", "needs some tlc"]},
            {"id": "supplemental_condition_009", "term": "renovation", "category": "condition", "aliases": []},
            {"id": "supplemental_condition_010", "term": "needs update", "category": "condition", "aliases": ["needs complete update"]},
            {"id": "supplemental_condition_011", "term": "modern", "category": "condition", "aliases": ["modern living"]},
            {"id": "supplemental_condition_012", "term": "updated flooring", "category": "condition", "aliases": ["upgraded flooring"]},
            {"id": "supplemental_condition_013", "term": "updated bathroom", "category": "condition", "aliases": ["updated bathrooms"]},
            {"id": "supplemental_condition_014", "term": "upgraded", "category": "condition", "aliases": ["upgraded kitchen"]},
            {"id": "supplemental_condition_015", "term": "well maintained", "category": "condition", "aliases": ["beautifully maintained"]},

            {"id": "supplemental_transaction_001", "term": "commercial property", "category": "transaction_or_listing", "aliases": []},
            {"id": "supplemental_transaction_002", "term": "mixed use commercial", "category": "transaction_or_listing", "aliases": []},
            {"id": "supplemental_transaction_003", "term": "home warranty", "category": "transaction_or_listing", "aliases": []},
            {"id": "supplemental_transaction_004", "term": "senior community", "category": "transaction_or_listing", "aliases": []},
            {"id": "supplemental_transaction_005", "term": "leased land", "category": "transaction_or_listing", "aliases": []},
            {"id": "supplemental_transaction_006", "term": "due diligence", "category": "transaction_or_listing", "aliases": []},
            {"id": "supplemental_transaction_007", "term": "financing", "category": "transaction_or_listing", "aliases": ["financing flexibility"]},
            {"id": "supplemental_transaction_008", "term": "licensed residential rehab", "category": "transaction_or_listing", "aliases": ["licensed residential rehab property"]},
            {"id": "supplemental_transaction_009", "term": "short term rental", "category": "transaction_or_listing", "aliases": []},

            {"id": "supplemental_room_001", "term": "kitchenette", "category": "room", "aliases": []},
            {"id": "supplemental_room_002", "term": "patio room", "category": "room", "aliases": []},
            {"id": "supplemental_room_003", "term": "mud room", "category": "room", "aliases": []},
            {"id": "supplemental_room_004", "term": "sunroom", "category": "room", "aliases": []},
            {"id": "supplemental_room_005", "term": "bunk room", "category": "room", "aliases": []},
            {"id": "supplemental_room_006", "term": "wine cellar", "category": "room", "aliases": []},
            {"id": "supplemental_room_007", "term": "formal dining area", "category": "room", "aliases": []},
            {"id": "supplemental_room_008", "term": "bedroom", "category": "room", "aliases": ["bedrooms"]},
            {"id": "supplemental_room_009", "term": "bathroom", "category": "room", "aliases": ["bathrooms"]},
            {"id": "supplemental_room_010", "term": "living room", "category": "room", "aliases": ["living area", "living areas"]},
            {"id": "supplemental_room_011", "term": "family room", "category": "room", "aliases": ["familly rom"]},
            {"id": "supplemental_room_012", "term": "chef's kitchen", "category": "room", "aliases": ["chef's kichen"]},
            {"id": "supplemental_room_013", "term": "in-law quarters", "category": "room", "aliases": ["in law quarter"]},
            {"id": "supplemental_room_014", "term": "formal dining room", "category": "room", "aliases": ["formal dinning room"]},
            {"id": "supplemental_room_015", "term": "breakfast nook", "category": "room", "aliases": []},
            {"id": "supplemental_room_016", "term": "en suite bathroom", "category": "room", "aliases": ["en suite bathroom", "en suite bath", "ensuite"]},
            {"id": "supplemental_room_017", "term": "laundry room", "category": "room", "aliases": ["laundry", "laundry area"]},
            {"id": "supplemental_room_018", "term": "home office", "category": "room", "aliases": ["office"]},
            {"id": "supplemental_room_019", "term": "dining area", "category": "room", "aliases": []},
            {"id": "supplemental_room_020", "term": "multigenerational living", "category": "room", "aliases": ["multi generational living", "multi-generational living"]},

            {"id": "supplemental_interior_001", "term": "tile shower", "category": "interior_feature", "aliases": []},
            {"id": "supplemental_interior_002", "term": "tile countertops", "category": "interior_feature", "aliases": []},
            {"id": "supplemental_interior_003", "term": "concrete countertops", "category": "interior_feature", "aliases": []},
            {"id": "supplemental_interior_004", "term": "bamboo floors", "category": "interior_feature", "aliases": []},
            {"id": "supplemental_interior_005", "term": "high-end finishes", "category": "interior_feature", "aliases": ["high end finishes"]},
            {"id": "supplemental_interior_006", "term": "natural light", "category": "interior_feature", "aliases": []},
            {"id": "supplemental_interior_007", "term": "air conditioning", "category": "interior_feature", "aliases": ["central air"]},
            {"id": "supplemental_interior_008", "term": "fireplace", "category": "interior_feature", "aliases": []},
            {"id": "supplemental_interior_009", "term": "hardwood floors", "category": "interior_feature", "aliases": ["hard wood floors"]},
            {"id": "supplemental_interior_010", "term": "double sinks", "category": "interior_feature", "aliases": []},
            {"id": "supplemental_interior_011", "term": "top floor", "category": "interior_feature", "aliases": []},
            {"id": "supplemental_interior_012", "term": "dishwasher", "category": "interior_feature", "aliases": []},
            {"id": "supplemental_interior_013", "term": "floor plan", "category": "interior_feature", "aliases": ["layout", "floor plans"]},

            {"id": "supplemental_exterior_001", "term": "veranda", "category": "exterior_feature", "aliases": []},
            {"id": "supplemental_exterior_002", "term": "cabana", "category": "exterior_feature", "aliases": []},
            {"id": "supplemental_exterior_003", "term": "fence", "category": "exterior_feature", "aliases": ["chain link fence"]},
            {"id": "supplemental_exterior_004", "term": "fenced", "category": "exterior_feature", "aliases": ["fenced in yards"]},
            {"id": "supplemental_exterior_005", "term": "garage", "category": "exterior_feature", "aliases": []},
            {"id": "supplemental_exterior_006", "term": "solar", "category": "exterior_feature", "aliases": ["paid solar panels"]},
            {"id": "supplemental_exterior_007", "term": "outdoor terrace", "category": "exterior_feature", "aliases": ["private outdoor terraces"]},
            {"id": "supplemental_exterior_008", "term": "barn", "category": "exterior_feature", "aliases": []},

            {"id": "supplemental_amenity_001", "term": "elevator", "category": "amenity", "aliases": ["elevator access"]},
            {"id": "supplemental_amenity_002", "term": "lounge", "category": "amenity", "aliases": ["residential lounge"]},
            {"id": "supplemental_amenity_003", "term": "boat dock", "category": "amenity", "aliases": ["private boat dock", "dock"]},
            {"id": "supplemental_amenity_004", "term": "community amenities", "category": "amenity", "aliases": ["amenities"]},
            {"id": "supplemental_amenity_005", "term": "building amenities", "category": "amenity", "aliases": []},
            {"id": "supplemental_amenity_006", "term": "walking trails", "category": "amenity", "aliases": ["walking hiking trails"]},
            {"id": "supplemental_amenity_007", "term": "swimming pool", "category": "amenity", "aliases": ["private swimming pool"]},

            {"id": "supplemental_location_001", "term": "shopping", "category": "location", "aliases": []},
            {"id": "supplemental_location_002", "term": "dining", "category": "location", "aliases": []},
            {"id": "supplemental_location_003", "term": "restaurants", "category": "location", "aliases": []},
            {"id": "supplemental_location_004", "term": "parks", "category": "location", "aliases": []},
            {"id": "supplemental_location_006", "term": "freeway", "category": "location", "aliases": ["freeways"]},
            {"id": "supplemental_location_007", "term": "views", "category": "location", "aliases": ["scenic views", "sweeping views"]},
            {"id": "supplemental_location_008", "term": "shops", "category": "location", "aliases": []},
            {"id": "supplemental_location_009", "term": "beach", "category": "location", "aliases": ["beaches"]},
            {"id": "supplemental_location_011", "term": "public transportation", "category": "location", "aliases": []},
            {"id": "supplemental_location_012", "term": "shopping center", "category": "location", "aliases": []},
            {"id": "supplemental_location_013", "term": "quiet neighborhood", "category": "location", "aliases": ["quiet local neighborhood", "quiet and friendly neighborhood"]},

            {"id": "supplemental_property_type_004", "term": "end unit", "category": "property_type", "aliases": []},
            {"id": "supplemental_property_type_005", "term": "corner unit", "category": "property_type", "aliases": []},
            {"id": "supplemental_property_type_006", "term": "cabin", "category": "property_type", "aliases": []},
            {"id": "supplemental_property_type_007", "term": "penthouse", "category": "property_type", "aliases": []},
        ]

    def _term_pattern(self, term):
        escaped = re.escape(term.lower())
        escaped = escaped.replace(r"\ ", r"\s+")
        escaped = escaped.replace(r"\-", r"[-\s]+")
        return re.compile(rf"(?<!\w){escaped}(?!\w)", flags=re.I)

    def _deduplicate_entities(self, entities):
        seen = set()
        deduped = []
        for entity in entities:
            value_key = json.dumps(entity.get("value"), sort_keys=True)
            key = (
                entity.get("label"),
                value_key,
                entity.get("start"),
                entity.get("end"),
                entity.get("method"),
                entity.get("source"),
            )
            if key not in seen:
                seen.add(key)
                deduped.append(entity)
        return deduped

    def _resolve_conflicts(self, entities):
        ranked = sorted(
            entities,
            key=lambda entity: (
                self.LABEL_PRIORITY.get(entity.get("label"), 9),
                self.METHOD_PRIORITY.get(entity.get("method"), 9),
                -(entity.get("end", 0) - entity.get("start", 0)),
                entity.get("start", 0),
            ),
        )

        selected = []
        for entity in ranked:
            if not self._has_conflict(entity, selected):
                selected.append(entity)

        return sorted(selected, key=lambda entity: (entity["start"], entity["end"], entity["label"]))

    def _has_conflict(self, entity, selected):
        for kept in selected:
            if self._same_span(entity, kept):
                return True
            if self._overlaps(entity, kept) and self._is_real_conflict(entity, kept):
                return True
        return False

    def _same_span(self, left, right):
        return left["start"] == right["start"] and left["end"] == right["end"]

    def _overlaps(self, left, right):
        return left["start"] < right["end"] and right["start"] < left["end"]

    def _is_real_conflict(self, left, right):
        if left["label"] == right["label"]:
            return True

        numeric_labels = {
            "price",
            "hoa_fee",
            "year_built",
            "sqft",
            "lot_size",
            "bedrooms",
            "bathrooms",
            "parking",
            "stories",
        }
        return left["label"] in numeric_labels or right["label"] in numeric_labels

    def _to_number(self, value):
        raw_value = str(value).strip().lower()
        if raw_value in self.NUMBER_WORDS:
            return self.NUMBER_WORDS[raw_value]

        number_text = re.sub(r"[,\s]", "", raw_value)
        number = float(number_text)
        return int(number) if number.is_integer() else number
