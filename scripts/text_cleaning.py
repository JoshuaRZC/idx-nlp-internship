import html
import re
import unicodedata
from collections import Counter


class TextCleaner:
    def __init__(self, abbrev_map=None):
        self.abbrev_map = self._default_abbrev_map()
        if abbrev_map:
            self.abbrev_map.update({k.lower(): v for k, v in abbrev_map.items()})

    def clean_text(self, text):
        text = "" if text is None else str(text)
        text = self.normalize_unicode(text)
        text = self.remove_html(text)
        text = self.normalize_case(text)
        text = self.normalize_prices(text)
        text = self.normalize_measurements(text)
        text = self.normalize_bed_bath_counts(text)
        text = self.normalize_parking(text)
        text = self.normalize_hoa(text)
        text = self.normalize_year_built(text)
        text = self.normalize_stories(text)
        text = self.expand_abbreviations(text)
        text = self.normalize_punctuation(text)
        text = self.normalize_whitespace(text)
        return text.strip()

    def clean_dataframe(self, df, source_column="remarks", target_column="remarks_cleaned"):
        df = df.copy()
        df[target_column] = df[source_column].apply(self.clean_text)
        return df

    def normalize_unicode(self, text):
        text = unicodedata.normalize("NFKC", str(text))
        replacements = {
            "\u00a0": " ",
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
            "\u2022": " ",
            "\u2026": "...",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def remove_html(self, text):
        text = html.unescape(str(text))
        text = text.replace("\u00a0", " ")
        text = re.sub(r"<\s*br\s*/?\s*>", " ", text, flags=re.I)
        text = re.sub(r"</\s*p\s*>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        return text

    def normalize_case(self, text):
        return str(text).lower()

    def normalize_prices(self, text):
        text = re.sub(
            r"(?:\$\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*k\b",
            lambda m: str(int(float(m.group(1).replace(",", "")) * 1000)),
            text,
            flags=re.I,
        )
        text = re.sub(
            r"(?:\$\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)\s*m\b",
            lambda m: str(int(float(m.group(1).replace(",", "")) * 1000000)),
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\$\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.00)?\b",
            lambda m: m.group(1).replace(",", ""),
            text,
        )
        return text

    def normalize_measurements(self, text):
        text = re.sub(
            r"\b(\d+)\s*/\s*(\d+)\s*(?:acres?|ac)\b",
            lambda m: f"{int(m.group(1)) / int(m.group(2)):g} acre",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\+?\s*(?:sq\.?\s*ft\.?|sqft|sf|s\.f\.|square\s*(?:feet|foot))(?=\W|$)",
            lambda m: f"{m.group(1).replace(',', '')} square feet",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*(?:acres?|acreage|ac)\b",
            r"\1 acre",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*(?:ft\.?|feet)\b",
            r"\1 foot",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:ft\.?|feet|foot)?\s*(?:lot|parcel|site)\b",
            r"\1 by \2 foot lot",
            text,
            flags=re.I,
        )
        return text

    def normalize_bed_bath_counts(self, text):
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*(full|half)\s*(?:ba|bth|bath|bathroom)s?\b",
            r"\1 \2 bathroom",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*(?:br|bd|bdrm|bdrms|beds?|bedrooms?)\b",
            r"\1 bedroom",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*(?:ba|bth|bths|baths?|bathrooms?)\b",
            r"\1 bathroom",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\b(?!\s*(?:acre|acres|ac\b))",
            r"\1 bedroom \2 bathroom",
            text,
        )
        return text

    def normalize_parking(self, text):
        text = re.sub(
            r"\b(\d+)\s*[- ]?\s*car\s+(attached|detached)?\s*(?:gar(?:age)?|garage)\b",
            lambda m: f"{m.group(1)} car {m.group(2) + ' ' if m.group(2) else ''}garage",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(\d+)\s*[- ]?\s*car\s*(?:pkg|prkg|parking|spaces?)\b",
            r"\1 car parking",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(\d+)\s+(assigned|covered|deeded|reserved|tandem)\s*(?:pkg|prkg|parking|spaces?)\b",
            r"\1 \2 parking",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\b(?:pkg|prkg)\s*(?:for\s*)?(\d+)\b",
            r"\1 parking",
            text,
            flags=re.I,
        )
        return text

    def normalize_hoa(self, text):
        text = re.sub(r"\bno\s+hoa\b", "no homeowners association", text, flags=re.I)
        text = re.sub(
            r"\bhoa\s*(?:dues?|fees?)?\s*(?:are|is|of)?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:/|per\s*)?(?:mo|month|monthly)\b",
            lambda m: f"homeowners association fee {m.group(1).replace(',', '')} per month",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\$?\s*\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:/|per\s*)?(?:mo|month|monthly)\s*(?:hoa|homeowners association)\b",
            lambda m: f"homeowners association fee {m.group(1).replace(',', '')} per month",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\bhoa\s*(?:dues?|fees?)\s*(?:included|incl)\b",
            "homeowners association fee included",
            text,
            flags=re.I,
        )
        text = re.sub(
            r"\bhoa\s+(?:includes?|incl)\b",
            "homeowners association includes",
            text,
            flags=re.I,
        )
        return text

    def normalize_year_built(self, text):
        year = r"((?:18|19|20)\d{2})"
        text = re.sub(
            rf"\b(?:yr|year)\s*(?:built|blt)\s*(?:in)?\s*{year}\b",
            r"year built \1",
            text,
            flags=re.I,
        )
        text = re.sub(
            rf"(?<!year )\b(?:built|blt|constructed)\s*(?:in)?\s*{year}\b",
            r"year built \1",
            text,
            flags=re.I,
        )
        text = re.sub(
            rf"\b{year}\s*(?:built|construction)\b",
            r"year built \1",
            text,
            flags=re.I,
        )
        return text

    def normalize_stories(self, text):
        number_words = {
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
        }
        text = re.sub(r"\bsingle\s*[- ]?(?:story|level)\b", "1 story", text, flags=re.I)
        text = re.sub(r"\bsplit\s*[- ]?level\b", "split level", text, flags=re.I)
        text = re.sub(r"\btri\s*[- ]?level\b", "3 level", text, flags=re.I)
        for word, number in number_words.items():
            text = re.sub(
                rf"\b{word}\s*[- ]?(?:story|stories|level|levels)\b",
                f"{number} story",
                text,
                flags=re.I,
            )
        text = re.sub(
            r"\b(\d+)\s*[- ]?(?:story|stories|level|levels)\b",
            r"\1 story",
            text,
            flags=re.I,
        )
        return text

    def expand_abbreviations(self, text):
        text = str(text)
        for abbrev in sorted(self.abbrev_map, key=len, reverse=True):
            replacement = self.abbrev_map[abbrev]
            if re.search(r"\w", abbrev):
                pattern = rf"(?<!\w){re.escape(abbrev)}(?!\w)"
            else:
                pattern = re.escape(abbrev)
            text = re.sub(pattern, replacement, text, flags=re.I)
        return text

    def normalize_punctuation(self, text):
        text = re.sub(r"[/|]", " ", text)
        text = re.sub(r"[;:]+", ", ", text)
        text = re.sub(r"[!?]{2,}", ".", text)
        text = re.sub(r"\.{2,}", ".", text)
        text = re.sub(r"\s*,\s*", ", ", text)
        text = re.sub(r"\s*-\s*", " ", text)
        text = re.sub(r"[^\w\s$.,'-]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def normalize_whitespace(self, text):
        return re.sub(r"\s+", " ", str(text)).strip()

    def profile_column(self, df, column_name):
        values = df[column_name].dropna().astype(str)
        return {
            "null_rate": df[column_name].isnull().mean(),
            "avg_length": values.str.len().mean(),
            "common_terms": self._extract_top_ngrams(values),
            "price_mentions": values.str.contains(r"\$\s*\d|\b\d+(?:\.\d+)?[km]\b", case=False).sum(),
            "has_html": values.str.contains(r"<[^>]+>|&(?:nbsp|amp|lt|gt);", case=False).sum(),
            "common_abbreviations": self._detect_abbreviations(values),
        }

    def _extract_top_ngrams(self, values, n=2, limit=20):
        counter = Counter()
        for text in values:
            words = re.findall(r"[a-zA-Z]{3,}", text.lower())
            counter.update(" ".join(words[i : i + n]) for i in range(len(words) - n + 1))
        return counter.most_common(limit)

    def _detect_abbreviations(self, values, limit=30):
        counter = Counter()
        patterns = {
            abbrev: re.compile(rf"(?<!\w){re.escape(abbrev)}(?!\w)", re.I)
            for abbrev in self.abbrev_map
        }
        for text in values:
            for abbrev, pattern in patterns.items():
                matches = pattern.findall(text)
                if matches:
                    counter[abbrev] += len(matches)
        return counter.most_common(limit)

    def _default_abbrev_map(self):
        return {
            "w/": "with",
            "w/o": "without",

            "bd": "bedroom",
            "bds": "bedrooms",
            "bdr": "bedroom",
            "bdrm": "bedroom",
            "bdrms": "bedrooms",
            "bedrm": "bedroom",
            "bedrms": "bedrooms",
            "br": "bedroom",
            "brs": "bedrooms",
            "ba": "bathroom",
            "bas": "bathrooms",
            "bth": "bathroom",
            "bths": "bathrooms",
            "bathrm": "bathroom",
            "bathrms": "bathrooms",
            "fb": "full bathroom",
            "hb": "half bathroom",
            "pb": "powder bathroom",
            "mbr": "master bedroom",
            "mstr": "master",
            "mstr br": "master bedroom",
            "mstr bdrm": "master bedroom",
            "prim br": "primary bedroom",
            "prim bdrm": "primary bedroom",
            "prim": "primary",
            "ens ba": "en suite bathroom",
            "ens bth": "en suite bathroom",
            "ens bath": "en suite bathroom",
            "ens": "en suite",

            "lr": "living room",
            "liv": "living",
            "liv rm": "living room",
            "lvg": "living",
            "lvg rm": "living room",
            "din": "dining",
            "din rm": "dining room",
            "dng": "dining",
            "dng rm": "dining room",
            "fr": "family room",
            "fam": "family",
            "fam rm": "family room",
            "gr": "great room",
            "gr rm": "great room",
            "rec": "recreation",
            "rec rm": "recreation room",
            "mud rm": "mud room",
            "pdr rm": "powder room",
            "rm": "room",

            "kit": "kitchen",
            "kits": "kitchens",
            "kitch": "kitchen",
            "kchn": "kitchen",
            "ktchn": "kitchen",
            "kitchn": "kitchen",
            "laund": "laundry",
            "ldry": "laundry",
            "lndry": "laundry",

            "pkg": "parking",
            "prkg": "parking",
            "prkng": "parking",
            "gar": "garage",
            "garag": "garage",
            "att gar": "attached garage",
            "det gar": "detached garage",
            "drvwy": "driveway",
            "drvway": "driveway",
            "crprt": "carport",

            "bkyd": "backyard",
            "bkyard": "backyard",
            "byard": "backyard",
            "yd": "yard",
            "fyd": "front yard",
            "front yd": "front yard",
            "rear yd": "rear yard",
            "pat": "patio",
            "cov pat": "covered patio",
            "balc": "balcony",
            "por": "porch",

            "fp": "fireplace",
            "fpl": "fireplace",
            "fplc": "fireplace",
            "frplc": "fireplace",
            "hw": "hardwood",
            "hwd": "hardwood",
            "hdwd": "hardwood",
            "flr": "floor",
            "flrs": "floors",
            "lvl": "level",
            "lvls": "levels",
            "ceil": "ceiling",
            "ceils": "ceilings",
            "vltd": "vaulted",
            "vault ceil": "vaulted ceiling",
            "hi ceil": "high ceiling",

            "appl": "appliance",
            "appls": "appliances",
            "apps": "appliances",
            "ss": "stainless steel",
            "s/s": "stainless steel",
            "stnls": "stainless",
            "gran": "granite",
            "cntr": "counter",
            "cntrs": "counters",
            "cab": "cabinet",
            "cabs": "cabinets",
            "dw": "dishwasher",
            "d/w": "dishwasher",
            "refrig": "refrigerator",
            "fridge": "refrigerator",
            "frdg": "refrigerator",
            "rng": "range",
            "w/d": "washer dryer",
            "w & d": "washer dryer",

            "hvac": "heating ventilation and air conditioning",
            "ac": "air conditioning",
            "a/c": "air conditioning",
            "c/a": "central air conditioning",
            "cac": "central air conditioning",
            "cent ac": "central air conditioning",
            "cent a/c": "central air conditioning",

            "hoa": "homeowners association",
            "hoas": "homeowners associations",
            "assoc": "association",
            "adu": "accessory dwelling unit",
            "jadu": "junior accessory dwelling unit",
            "pud": "planned unit development",
            "sfr": "single family residence",
            "sfh": "single family home",
            "twnhm": "townhome",
            "twnhse": "townhouse",

            "yr": "year",
            "yrs": "years",
            "blt": "built",
            "mo": "month",
            "mos": "months",
            "mins": "minutes",
            "min": "minute",
            "dist": "distance",
            "approx": "approximately",
            "apx": "approximately",
            "appt": "appointment",
            "avail": "available",
            "incl": "included",
            "inc": "included",
            "excl": "excluded",
            "neg": "negotiable",

            "sch": "school",
            "schs": "schools",
            "elem": "elementary",
            "ele": "elementary",
            "mid": "middle",
            "jr": "junior",
            "sr": "senior",
            "hs": "high school",
            "frwy": "freeway",
            "hwy": "highway",
            "nbhd": "neighborhood",
            "nbrhd": "neighborhood",
            "nhood": "neighborhood",

            "ctr": "center",
            "renov": "renovated",
            "reno": "renovated",
            "remod": "remodeled",
            "upd": "updated",
            "updt": "updated",
            "upgr": "upgraded",
            "orig": "original",
            "cond": "condition",
            "loc": "location",
            "prop": "property",
            "desc": "description",
            "pic": "picture",
            "pics": "pictures",
            "info": "information",
            "co": "company",
            "reo": "real estate owned",
            "fsbo": "for sale by owner",
            "dom": "days on market",
            "unit #": "unit number ",
            "#": "number ",
        }
