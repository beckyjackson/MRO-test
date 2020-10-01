import csv
import re
import sys

from argparse import ArgumentParser


err_id = 0


def check_labels(table_name, reader, label_source, valid_labels, regex=None):
    """Check that the labels used in a table are all present in a set of valid labels. If provided,
    also match the labels to a regex pattern. Return all labels from the table and a set of errors,
    if any."""
    global err_id
    errors = []
    row_idx = 3
    headers = reader.fieldnames
    labels = []
    for row in reader:
        label = row["Label"]
        labels.append(label)
        if label not in valid_labels:
            err_id += 1
            errors.append(
                {
                    "ID": err_id,
                    "table": table_name,
                    "cell": idx_to_a1(row_idx, headers.index("Label") + 1),
                    "level": "error",
                    "rule ID": "unknown_label",
                    "rule name": "unknown label",
                    "value": label,
                    "instructions": f"use a label defined in {label_source}",
                }
            )
        if regex and not re.match(regex, label):
            err_id += 1
            errors.append(
                {
                    "ID": err_id,
                    "table": table_name,
                    "cell": idx_to_a1(row_idx, headers.index("Label") + 1),
                    "level": "error",
                    "rule ID": "invalid_label",
                    "rule name": "invalid label",
                    "value": label,
                    "instructions": f"change label to match pattern '{regex}'",
                }
            )
        row_idx += 1
    return labels, errors


def check_fields(
    table_name,
    reader,
    valid_labels,
    field_name="Parent",
    top_term=None,
    source=None,
    required=True,
):
    """Validate that the contents of a given field (default=Parent) are present in a set of valid
    labels. If required, validate that this field value is filled in for all rows. Return a set of
    errors, if any."""
    global err_id
    errors = []
    row_idx = 3
    headers = reader.fieldnames
    if not source:
        source = table_name
    for row in reader:
        value = row[field_name]
        if value and value.strip() == "":
            value = None

        if value:
            value = value.strip()

        if required and not value:
            err_id += 1
            errors.append(
                {
                    "ID": err_id,
                    "table": table_name,
                    "cell": idx_to_a1(row_idx, headers.index(field_name) + 1),
                    "level": "error",
                    "rule ID": f"missing_required_{field_name.lower().replace(' ', '_')}",
                    "rule name": f"missing required '{field_name}'",
                    "instructions": f"add a '{field_name}' term",
                }
            )
        if value and value != top_term and value not in valid_labels:
            err_id += 1
            errors.append(
                {
                    "ID": err_id,
                    "table": table_name,
                    "cell": idx_to_a1(row_idx, headers.index(field_name) + 1),
                    "level": "error",
                    "rule ID": f"invalid_{field_name.lower().replace(' ', '_')}",
                    "rule name": f"invalid '{field_name}'",
                    "value": value,
                    "instructions": f"replace the '{field_name}' with a term from {source}",
                }
            )
        row_idx += 1
    return errors


def check_restriction_level(table_name, reader, valid_levels):
    """"""
    global err_id
    row_idx = 3
    headers = reader.fieldnames
    errors = []
    for row in reader:
        res_level = row["Restriction Level"]
        if res_level not in valid_levels:
            err_id += 1
            errors.append(
                {
                    "ID": err_id,
                    "table": table_name,
                    "cell": idx_to_a1(row_idx, headers.index("Restriction Level") + 1),
                    "level": "error",
                    "rule ID": "invalid_restriction_level",
                    "rule name": "invalid restriction level",
                    "value": res_level,
                    "instructions": "change the restriction level to one of: "
                    + ", ".join(valid_levels),
                }
            )
    return errors


def idx_to_a1(row, col):
    """Convert a row & column to A1 notation. Adapted from gspread.utils."""
    div = col
    column_label = ""

    while div:
        (div, mod) = divmod(div, 26)
        if mod == 0:
            mod = 26
            div -= 1
        column_label = chr(mod + 64) + column_label

    return f"{column_label}{row}"


def validate_chain(template_dir, labels, genetic_locus_labels):
    """Validate chain.tsv. This checks that:
    - All labels are present in index and end with 'chain'
    - All terms have a parent that is present in this sheet OR is 'protein'
    - All terms with parent 'protein' have a 'Gene' and the 'Gene' is from genetic-locus.tsv

    Return all the labels from this sheet and a set of errors, if any."""
    global err_id
    table_name = "chain"
    errors = []
    with open(f"{template_dir}/{table_name}.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        next(reader)

        # Get the labels for all chains
        # and validate that those labels end with "chain" and are present in index
        chain_labels, label_errors = check_labels(
            table_name, reader, "index", labels, regex=r"^.+ chain$"
        )
        errors.extend(label_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate parents
        parent_errors = check_fields(table_name, reader, chain_labels, top_term="protein")
        errors.extend(parent_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)
        row_idx = 3

        # Validate specifics to chain.tsv
        for row in reader:
            # The gene is required when parent == protein
            # The gene should occur in the genetic-locus sheet
            # Don't use check_fields because it is only required when parent == protein
            parent = row["Parent"]
            gene = row["Gene"]
            if not gene or gene.strip == "":
                if parent == "protein":
                    err_id += 1
                    errors.append(
                        {
                            "ID": err_id,
                            "table": table_name,
                            "cell": idx_to_a1(row_idx, headers.index("Gene") + 1),
                            "level": "error",
                            "rule ID": "missing_chain_gene",
                            "rule name": "missing chain gene with 'protein' parent",
                            "instructions": f"add a 'Gene' from genetic-locus",
                        }
                    )
            elif gene not in genetic_locus_labels:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("Gene") + 1),
                        "level": "error",
                        "rule ID": "invalid_chain_gene",
                        "rule name": "invalid chain gene",
                        "instructions": f"replace the 'Gene' with a term from genetic-locus",
                    }
                )

            row_idx += 1
    return chain_labels, errors


def validate_chain_sequence(template_dir, chain_labels):
    """Validate chain-sequence.tsv. This checks that:
    - All labels are present in chain.tsv

    Return a set of errors, if any."""
    errors = []
    with open(f"{template_dir}/chain-sequence.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        next(reader)

        # Validate that those labels are present in chain
        # No need to retrieve labels because they're duplicate of those in chain
        _, label_errors = check_labels("chain-sequence", reader, "chain", chain_labels)
        errors.extend(label_errors)
    return errors


def validate_genetic_locus(template_dir, labels, external_labels):
    """Validate genetic-locus.tsv. This checks that:
    - All labels are present in index.tsv and end with 'locus'
    - All terms have parents that are present in this sheet OR is 'MHC locus'
    - Any "In Taxon" value is present in external.tsv

    Return the labels from this sheet and a set of errors, if any."""
    global err_id
    table_name = "genetic-locus"
    errors = []
    with open(f"{template_dir}/{table_name}.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        next(reader)

        # Get the labels for all genetic loci
        # and validate that those labels end with "locus" and are present in index
        genetic_locus_labels, label_errors = check_labels(
            table_name, reader, "index", labels, regex=r"^.+ locus$"
        )
        errors.extend(label_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate parents
        parent_errors = check_fields(
            table_name, reader, genetic_locus_labels, top_term="MHC locus"
        )
        errors.extend(parent_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)
        row_idx = 3

        # Validate taxon
        for row in reader:
            taxon = row["In Taxon"]
            if taxon.strip == "":
                taxon = None

            if taxon and taxon not in external_labels:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "invalid_taxon",
                        "rule name": "invalid taxon",
                        "value": taxon,
                        "instructions": "add this taxon to 'external' or "
                        "replace it with a taxon from 'external'",
                    }
                )

    return genetic_locus_labels, errors


def validate_halpotype(template_dir, labels, external_labels):
    """Validate haplotype.tsv. This checks that:
    - All labels are present in index.tsv and end with 'haplotype'
    - All terms have a parent that is present in this sheet OR is 'MHC haplotype'
    - An 'In Taxon' value is present when the parent is 'MHC haplotype'
      and this is present in external.tsv

    Return all labels from this sheet and a set of errors, if any."""
    global err_id

    table_name = "haplotype"
    errors = []
    with open(f"{template_dir}/{table_name}.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        next(reader)

        # Get the labels for all haplotypes
        # and validate that those labels end with "haplotype" and are present in index
        haplotype_labels, label_errors = check_labels(
            table_name, reader, "index", labels, regex=r"^.+ haplotype$"
        )
        errors.extend(label_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        parent_errors = check_fields(
            table_name, reader, haplotype_labels, top_term="MHC haplotype"
        )
        errors.extend(parent_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)
        row_idx = 3

        # Validate "In Taxon" values
        for row in reader:
            parent = row["Parent"]
            if parent.strip() == "":
                parent = None
            taxon = row["In Taxon"]
            if taxon.strip() == "":
                taxon = None

            if parent == "MHC haplotype" and not taxon:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "missing_required_taxon",
                        "rule name": "missing required taxon for 'MHC haplotype' parent",
                        "instructions": "add a taxon from 'external'",
                    }
                )

            if taxon and taxon not in external_labels:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "invalid_taxon",
                        "rule name": "invalid taxon",
                        "value": taxon,
                        "instructions": "add this taxon to 'external' or "
                        "replace it with a taxon from 'external'",
                    }
                )
    return haplotype_labels, errors


def validate_haplotype_molecule(
    template_dir, labels, molecule_labels, haplotype_labels, external_labels
):
    """Validate haplotype-molecule.tsv. This checks that:
    - All labels are present in index.tsv and end with 'with X haplotype' or 'with haplotype'
    - All terms have a parent that is present in molecule.tsv
    - The 'Restriction Level' is 'haplotype'
    - All terms have an "In Taxon" value that is present in external.tsv
    - All terms have a "With Haplotype" value that is present in haplotype.tsv

    Return a set of errors, if any."""
    global err_id
    table_name = "haplotype-molecule"
    errors = []
    with open(f"{template_dir}/{table_name}.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        next(reader)

        # Get any labels not defined in index
        _, label_errors = check_labels(
            table_name,
            reader,
            "index",
            labels,
            regex=r"^.+ (with haplotype|with [^ ]+ haplotype)$",
        )
        errors.extend(label_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate parents (from molecule table)
        parent_errors = check_fields(
            table_name,
            reader,
            molecule_labels,
            top_term="MHC protein complex",
            source="molecule",
        )
        errors.extend(parent_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate with haplotype
        with_haplotype_errors = check_fields(
            table_name,
            reader,
            haplotype_labels,
            top_term="MHC haplotype",
            field_name="With Haplotype",
            source="haplotype",
        )
        errors.extend(with_haplotype_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate restriction levels
        res_level_errors = check_restriction_level(table_name, reader, ["haplotype"])
        errors.extend(res_level_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)
        row_idx = 3

        # Validate taxon
        for row in reader:
            taxon = row["In Taxon"]
            if taxon.strip == "":
                taxon = None

            if not taxon:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "missing_required_taxon",
                        "rule name": "missing required taxon",
                        "instructions": "add a taxon from 'external'",
                    }
                )

            elif taxon not in external_labels:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "invalid_taxon",
                        "rule name": "invalid taxon",
                        "value": taxon,
                        "instructions": "add this taxon to 'external' or "
                        "replace it with a taxon from 'external'",
                    }
                )
    return errors


def validate_iedb_labels(iedb_path, labels):
    """Validate iedb.tsv. This checks that all labels are present in index.tsv. Return a set of
    errors, if any."""
    with open(iedb_path, "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        next(reader)
        _, errors = check_labels("iedb", reader, "index", labels)
    return errors


def validate_molecule(
    template_dir,
    labels,
    chain_labels,
    external_labels,
    haplotype_labels,
    serotype_labels,
):
    """Validate molecule.tsv. This checks that:
    - All labels are present in index.tsv and end with 'protein complex'
    - All terms have parents that are present in this sheet OR is 'MHC protein complex'
    - The 'Restriction Level' is one of: class, complete molecule, locus, partial molecule
    - An 'In Taxon' value is present when the parent is NOT 'MHC protein complex'
      and this value is present in external.tsv
    - The 'Alpha Chain' value is present in chain.tsv
    - The 'Beta Chain' value is present in chain.tsv OR is 'Beta-2-microglobulin'
    - The 'With Haplotype' value is present in haplotype.tsv
    - The 'With Serotype' value is present in serotype.tsv

    Return all labels from this sheet and a set of errors, if any."""
    global err_id
    table_name = "molecule"
    errors = []
    with open(f"{template_dir}/molecule.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        next(reader)

        # Get the labels for all genetic loci
        # and validate that those labels end with "locus" and are present in index
        molecule_labels, label_errors = check_labels(
            "molecule", reader, "index", labels, regex=r"^.+ protein complex$"
        )
        errors.extend(label_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate parents
        parent_errors = check_fields(
            table_name, reader, molecule_labels, top_term="MHC protein complex"
        )
        errors.extend(parent_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Alpha chain must be in chain labels
        alpha_errors = check_fields(
            table_name,
            reader,
            chain_labels,
            field_name="Alpha Chain",
            source="chain",
            required=False,
        )
        errors.extend(alpha_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Beta chain must be in chain labels or Beta-2-microglobulin
        beta_errors = check_fields(
            table_name,
            reader,
            chain_labels,
            field_name="Beta Chain",
            top_term="Beta-2-microglobulin",
            source="chain",
            required=False,
        )
        errors.extend(beta_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # With haplotype is in haplotype
        haplotype_errors = check_fields(
            table_name,
            reader,
            haplotype_labels,
            field_name="With Haplotype",
            source="haplotype",
            required=False,
        )
        errors.extend(haplotype_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # With serotype is in serotype
        serotype_errors = check_fields(
            table_name,
            reader,
            serotype_labels,
            field_name="With Serotype",
            source="serotype",
            required=False,
        )
        errors.extend(serotype_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate restriction levels
        res_level_errors = check_restriction_level(
            table_name,
            reader,
            [
                "class",
                "locus",
                "complete molecule",
                "partial molecule",
            ],
        )
        errors.extend(res_level_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)
        row_idx = 3

        # Restriction level must be one of: locus, complete molecule, partial molecule
        # Taxon required when parent NOT MHC protein complex
        for row in reader:
            parent = row["Parent"]
            taxon = row["In Taxon"]
            if taxon.strip == "":
                taxon = None

            if parent != "MHC protein complex" and not taxon:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "missing_required_taxon",
                        "rule name": "missing required taxon for parent other than "
                        "'MHC protein complex'",
                        "instructions": "add a taxon from 'external'",
                    }
                )

            elif taxon and taxon not in external_labels:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "invalid_taxon",
                        "rule name": "invalid taxon",
                        "value": taxon,
                        "instructions": "add this taxon to 'external' or "
                        "replace it with a taxon from 'external'",
                    }
                )

    return molecule_labels, errors


def validate_mutant_molecule(template_dir, labels, external_labels, molecule_labels):
    """Validate mutant-molecule.tsv. This checks that:
    - All labels are present in index.tsv and end with 'protein complex'
    - All terms have parents that are present in this sheet OR is 'mutant MHC protein complex'
    - The 'Restriction Level' is one of: class, complete molecule, partial molecule
    - The 'In Taxon' value is in external.tsv
    - The 'Mutant Of' value is in molecule.tsv

    Return a set of errors, if any."""
    global err_id
    table_name = "mutant-molecule"
    errors = []
    with open(f"{template_dir}/{table_name}.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        next(reader)

        # Get any labels not defined in index
        mutant_molecule_labels, label_errors = check_labels(
            table_name, reader, "index", labels, regex=r"^.+ protein complex$"
        )
        errors.extend(label_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate parents
        parent_errors = check_fields(
            table_name,
            reader,
            mutant_molecule_labels,
            top_term="mutant MHC protein complex",
        )
        errors.extend(parent_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate "Mutant Of" fields
        molecule_errors = check_fields(
            table_name,
            reader,
            molecule_labels,
            field_name="Mutant Of",
            source="molecule",
            required=False,
        )
        errors.extend(molecule_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate restriction levels
        res_level_errors = check_restriction_level(
            table_name, reader, ["class", "complete molecule", "partial molecule"]
        )
        errors.extend(res_level_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)
        row_idx = 3

        # Taxon required when parent NOT MHC protein complex
        for row in reader:
            taxon = row["In Taxon"]
            if taxon.strip == "":
                taxon = None

            if taxon and taxon not in external_labels:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "invalid_taxon",
                        "rule name": "invalid taxon",
                        "value": taxon,
                        "instructions": "add this taxon to 'external' or "
                        "replace it with a taxon from 'external'",
                    }
                )
    return errors


def validate_serotype(template_dir, labels, external_labels):
    """Validate serotype.tsv. This checks that:
    - All labels are present in index.tsv and end with 'serotype'
    - All terms have parents that are present in this sheet OR is 'MHC serotype'
    - The 'In Taxon' value is present in external.tsv

    Return all labels from this sheet and a set of errors, if any.
    - """
    global err_id
    table_name = "serotype"
    errors = []
    with open(f"{template_dir}/{table_name}.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        next(reader)

        # Get the labels for all serotypes
        # and validate that those labels end with "serotype" and are present in index
        serotype_labels, label_errors = check_labels(
            table_name, reader, "index", labels, regex=r"^.+ serotype$"
        )
        errors.extend(label_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate parents
        parent_errors = check_fields(
            table_name, reader, serotype_labels, top_term="MHC serotype"
        )
        errors.extend(parent_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)
        row_idx = 3

        # Validate taxon in 'external'
        for row in reader:
            taxon = row["In Taxon"]
            if taxon and taxon.strip() == "":
                taxon = None

            if taxon and taxon not in external_labels:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "invalid_taxon",
                        "rule name": "invalid taxon",
                        "value": taxon,
                        "instructions": "add this taxon to 'external' or "
                        "replace it with a taxon from 'external'",
                    }
                )
    return serotype_labels, errors


def validate_serotype_molecule(
    template_dir, labels, external_labels, molecule_labels, serotype_labels
):
    """Validate serotype-molecule.tsv. This checks that:
    - All labels are present in index.tsv and end with 'with X serotype' or 'with serotype'
    - All terms have parents that are present in molecule.tsv
    - The 'Restriction Level' value is 'serotype'
    - The 'In Taxon' value is present in external.tsv
    - All terms have 'With Serotype' values that are present in serotype.tsv

    Return a set of errors, if any."""
    global err_id
    table_name = "serotype-molecule"
    errors = []
    with open(f"{template_dir}/{table_name}.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        next(reader)

        _, label_errors = check_labels(
            table_name,
            reader,
            "index",
            labels,
            regex=r"^.+ (with serotype|with [^ ]+ serotype)$",
        )
        errors.extend(label_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate parents (from molecule)
        parent_errors = check_fields(
            table_name,
            reader,
            molecule_labels,
            top_term="MHC protein complex",
            source="molecule",
        )
        errors.extend(parent_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        with_serotype_errors = check_fields(
            table_name,
            reader,
            serotype_labels,
            field_name="With Serotype",
            source="serotype",
        )
        errors.extend(with_serotype_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)

        # Validate restriction levels
        res_level_errors = check_restriction_level(table_name, reader, ["serotype"])
        errors.extend(res_level_errors)

        # Reset file to beginning
        f.seek(0)
        next(reader)
        next(reader)
        row_idx = 3

        # Validate taxon
        for row in reader:
            taxon = row["In Taxon"]
            if taxon.strip == "":
                taxon = None

            if taxon and taxon not in external_labels:
                err_id += 1
                errors.append(
                    {
                        "ID": err_id,
                        "table": table_name,
                        "cell": idx_to_a1(row_idx, headers.index("In Taxon") + 1),
                        "level": "error",
                        "rule ID": "invalid_taxon",
                        "rule name": "invalid taxon",
                        "value": taxon,
                        "instructions": "add this taxon to 'external' or "
                        "replace it with a taxon from 'external'",
                    }
                )
    return errors


def main():
    p = ArgumentParser()
    p.add_argument("index")
    p.add_argument("iedb")
    p.add_argument("template_dir")
    p.add_argument("err_output")
    args = p.parse_args()

    template_dir = args.template_dir

    # Get MRO labels defined in the index
    labels = []
    with open(args.index, "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        next(reader)
        for row in reader:
            labels.append(row["Label"])

    # Get imported term labels
    ext_labels = []
    with open(f"{template_dir}/external.tsv", "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        next(reader)
        for row in reader:
            ext_labels.append(row["Label"])

    errors = []

    # Validate the IEDB table
    iedb_errors = validate_iedb_labels(args.iedb, labels)
    errors.extend(iedb_errors)

    # Validate genetic-locus
    genetic_locus_labels, genetic_locus_errors = validate_genetic_locus(
        template_dir, labels, ext_labels
    )

    # Validate chain
    chain_labels, chain_errors = validate_chain(
        template_dir, labels, genetic_locus_labels
    )

    # Validate chain-sequence
    chain_sequence_errors = validate_chain_sequence(template_dir, chain_labels)

    # Vaildate haplotype
    haplotype_labels, haplotype_errors = validate_halpotype(
        template_dir, labels, ext_labels
    )

    # Validate serotype
    serotype_labels, serotype_errors = validate_serotype(
        template_dir, labels, ext_labels
    )

    # Validate molecule
    molecule_labels, molecule_errors = validate_molecule(
        template_dir,
        labels,
        chain_labels,
        ext_labels,
        haplotype_labels,
        serotype_labels,
    )

    # Validate mutant-molecule
    mutant_molecule_errors = validate_mutant_molecule(
        template_dir, labels, ext_labels, molecule_labels
    )

    # Validate haplotype-moleculee
    haplotype_molecule_errors = validate_haplotype_molecule(
        template_dir, labels, molecule_labels, haplotype_labels, ext_labels
    )

    # Validate serotype-molecule
    serotype_molecule_errors = validate_serotype_molecule(
        template_dir, labels, ext_labels, molecule_labels, serotype_labels
    )

    # Add errors in tabel order
    errors.extend(chain_errors)
    errors.extend(chain_sequence_errors)
    errors.extend(genetic_locus_errors)
    errors.extend(haplotype_errors)
    errors.extend(haplotype_molecule_errors)
    errors.extend(molecule_errors)
    errors.extend(mutant_molecule_errors)
    errors.extend(serotype_errors)
    errors.extend(serotype_molecule_errors)

    with open(args.err_output, "w") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ID",
                "table",
                "cell",
                "level",
                "rule ID",
                "rule name",
                "value",
                "fix",
                "instructions",
            ],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(errors)

    if errors:
        print(f"ERROR: Validation failed with {err_id} error(s)")
        sys.exit(1)


if __name__ == "__main__":
    main()
