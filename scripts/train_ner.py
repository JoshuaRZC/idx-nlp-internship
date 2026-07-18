import argparse
import json
import random
import warnings
from pathlib import Path

import spacy
from spacy.training import offsets_to_biluo_tags
from spacy.training import Example
from spacy.util import minibatch


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


def load_items(path):
    with Path(path).open() as f:
        return json.load(f)["items"]


def entity_tuple(entity):
    return entity["start"], entity["end"], entity["label"]


def resolve_overlaps(entities):
    ranked = sorted(
        entities,
        key=lambda entity: (
            -(entity["end"] - entity["start"]),
            LABEL_PRIORITY.get(entity["label"], 9),
            entity["start"],
        ),
    )

    selected = []
    for entity in ranked:
        if any(overlaps(entity, kept) for kept in selected):
            continue
        selected.append(entity)

    return sorted(selected, key=lambda entity: (entity["start"], entity["end"]))


def overlaps(left, right):
    return left["start"] < right["end"] and right["start"] < left["end"]


def aligned_entities(nlp, text, entities):
    doc = nlp.make_doc(text)
    aligned = []

    for entity in entities:
        candidate = entity_tuple(entity)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            tags = offsets_to_biluo_tags(doc, [candidate])
        if "-" not in tags:
            aligned.append(candidate)

    return aligned


def to_examples(nlp, items, training=True):
    examples = []
    for item in items:
        entities = aligned_entities(nlp, item["text"], resolve_overlaps(item["entities"]))
        if training:
            doc = nlp.make_doc(item["text"])
            examples.append(Example.from_dict(doc, {"entities": entities}))
        else:
            predicted = nlp(item["text"])
            reference = Example.from_dict(
                nlp.make_doc(item["text"]),
                {"entities": entities},
            ).reference
            examples.append(Example(predicted, reference))
    return examples


def count_training_spans(nlp, items):
    total = 0
    kept = 0
    for item in items:
        entities = resolve_overlaps(item["entities"])
        total += len(entities)
        kept += len(aligned_entities(nlp, item["text"], entities))
    return total, kept


def labels_from_items(items):
    labels = set()
    for item in items:
        for entity in item["entities"]:
            labels.add(entity["label"])
    return sorted(labels)


def train_model(train_items, dev_items, iterations, dropout, seed):
    random.seed(seed)
    nlp = spacy.blank("en")
    ner = nlp.add_pipe("ner")

    for label in labels_from_items(train_items + dev_items):
        ner.add_label(label)

    train_examples = to_examples(nlp, train_items)
    train_total, train_kept = count_training_spans(nlp, train_items)
    dev_total, dev_kept = count_training_spans(nlp, dev_items)
    print(f"train spans kept: {train_kept}/{train_total}", flush=True)
    print(f"dev spans kept: {dev_kept}/{dev_total}", flush=True)

    optimizer = nlp.initialize(lambda: train_examples)

    for epoch in range(1, iterations + 1):
        random.shuffle(train_examples)
        losses = {}
        for batch in minibatch(train_examples, size=16):
            nlp.update(batch, sgd=optimizer, drop=dropout, losses=losses)
        print(f"epoch {epoch:02d} ner_loss={losses.get('ner', 0):.2f}", flush=True)

    scores = nlp.evaluate(to_examples(nlp, dev_items, training=False))
    return nlp, scores


def parse_args():
    parser = argparse.ArgumentParser(description="Train a spaCy NER model for listing entities.")
    parser.add_argument(
        "--train",
        default="data/processed/entity_train_labels.json",
        help="Reviewed train labels.",
    )
    parser.add_argument(
        "--dev",
        default="data/processed/entity_dev_labels.json",
        help="Reviewed dev labels.",
    )
    parser.add_argument(
        "--output",
        default="data/models/entity_ner",
        help="Output directory for the trained model.",
    )
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    train_items = load_items(args.train)
    dev_items = load_items(args.dev)

    nlp, scores = train_model(train_items, dev_items, args.iterations, args.dropout, args.seed)
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    nlp.to_disk(output_path)

    print(f"saved model to {output_path}", flush=True)
    print(f"ents_p={scores['ents_p']:.3f}", flush=True)
    print(f"ents_r={scores['ents_r']:.3f}", flush=True)
    print(f"ents_f={scores['ents_f']:.3f}", flush=True)


if __name__ == "__main__":
    main()
