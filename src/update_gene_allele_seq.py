import csv
import os
from Bio import SeqIO
from Bio.Data.CodonTable import TranslationError as TError
import json
import argparse
import subprocess
import sys
import re
import pandas as pd
# gen_records = {}
# records_list = [seq_record for seq_record in SeqIO.parse(os.path.join("/Users/amody/IMGTHLA/fasta",  "hla_gen.fasta"), "fasta")]
# for record in records_list:
#     stuff = record.description.split(" ")
#     record.id = stuff[0][4:]
#     record.name = stuff[1]
# gen_records.update(SeqIO.to_dict(records_list, key_function = lambda rec: rec.name))

EXCLUDED_GENES = {
    "BTN3A",
    "CD1",
    "DOA",
    "DOB",
    "V",
    "P",
    "S",
    "Y",
    "MICA",
    "MICB",
    "MR1",
    "HFE",
    "J",
    "L",
    "TAP1",
    "DMB",
    "DMA",
    "T",
    "V",
    "W",
    "K",
    "TAP2",
    "U",
    "H",
    "DRB8",
    "DRB9",
    "DRB7",
    "DRB6",
    "DPB2",
    "DPA2",
    "DQA2",
    "DRB2"
}
def get_chains():
    se = open("ontology/chain-sequence.tsv", "r")
    next(se)
    rows = csv.DictReader(se, delimiter="\t")
    chains = {row["LABEL"].split(" ")[0]: row["A MRO:sequence"] for row in rows}
    return chains
#nuc_records = {}

# m = []
# for i in rec:
#
#     types = [feature.type for feature in i.features]
#     if "CDS" not in types:
#         print(i.description)
#         m.append(str((i.name, i.description)))
# print("\n".join(m))

def get_G_groups():
    gen_seq = {}
    p = open("build/hla_nom_g.txt", "r")
    c = p.read().splitlines()
    for i in c:
        if i.startswith("#"):
            continue
        yt = i.split(";")
        locus = yt[0]
        alleles = yt[1].split("/")
        alleles = ["HLA-" + locus + allele for allele in alleles]
        if len(yt) > 2 and len(yt[2]) > 0:
            G_grp = "HLA-" + locus + yt[2]
            gen_seq.update({allele : G_grp for allele in alleles})
    return gen_seq

def update_allele_dict(allele_dict):
    allele_dict["MHC gene allele"] = allele_dict["MHC gene allele"] + " gene allele"
    allele_dict["Subclass"] = "MHC gene allele"
    return allele_dict

def process_hla_dat(gen_seq, gene_allele_fields,chains ):
    errors = []
    gen_alleles = []
    G_groups = {}
    rec = SeqIO.parse("build/hla.dat", "imgt")
    for b in rec:
        try:
            gene_allele = {}
            allele, mhc_class = b.description.split(",")
            mhc_class = ("II" if "II" in mhc_class else "I")
            gene_allele["MHC gene allele"] = allele
            if allele.split("*")[0].split("-")[1] in EXCLUDED_GENES or allele.endswith("N") or allele.endswith("Q"):
                continue
            if mhc_class == "I":
                exons = [str(feature.extract(b).seq) for feature in b.features if feature.type == 'exon' and (feature.qualifiers['number'] == ['2'] or feature.qualifiers['number'] == ['3'])]
                exons = "|".join(exons)
            else:
                exons = [str(feature.extract(b).seq) for feature in b.features if feature.type == 'exon' and (feature.qualifiers['number'] == ['2'])]
                exons = exons[0]
            if allele in gen_seq and gen_seq[allele]:
                G_groups.setdefault(gen_seq[allele], set()).add(exons)
            cds = [feature for feature in b.features if feature.type=='CDS' and feature.location is not None and 'translation' in feature.qualifiers]
            if len(cds) == 1:
                cds = cds[0]
            else:
                continue
            gene_allele["Coding Region Sequence"] = str(cds.extract(b).seq)
            gene_allele["Source"] = "IMGT/HLA"
            gene_allele["Accession"] = b.name
            locus = allele.split("*")[0]
            match = re.search(pattern = r"[0-9]+$", string=locus)
            if match:
                locus = locus[:match.span()[0]]

            gene_allele["Locus"] = locus + " locus"
            two_field = allele.split(":")
            two_field = two_field[0] + ":" + two_field[1]
            if two_field in chains:
                #if chains[two_field] == cds.extract(b).seq[int(cds.qualifiers['codon_start'][0])-1:].translate():
                if str(cds.translate(b).seq) in chains[two_field] or chains[two_field] in str(cds.translate(b).seq):
                    gene_allele["Chain"] = two_field + " chain"
                else:
                    error = {"reason":"MRO protein not equal to IMGT protein", "IMGT Accession": b.name, "MRO allele": two_field, "MRO protein": chains[two_field], "Translated Protein": str(cds.translate(b).seq)   }
                    errors.append(error)
            else:
                error = {"reason": "MRO doesn't have allele", "IMGT Accession": b.name, "IMGT allele" : allele, "MRO allele": two_field}
                errors.append(error)
        except AttributeError:
            error = {"reason" : "AttributeError", "IMGT Accession": b.name, "IMGT allele" : allele}
            errors.append(error)
            continue
        except IndexError:
            error = {"reason" : "IndexError", "IMGT Accession": b.name, "IMGT allele" : allele}
            errors.append(error)
            continue
        except TError:
            # mainly for alleles with partial sequences
            #print("TranslationError", b.name)
            extracted_protein = cds.qualifiers["translation"][0]
            extracted_protein = str(extracted_protein)
            if chains[two_field] in extracted_protein or extracted_protein in chains[two_field]:
                gene_allele["Chain"] = two_field + " chain"
            else:
                error = {"reason" : "TranslationError", "IMGT Accession": b.name, "IMGT allele" : allele}
                errors.append(error)
        if allele in gen_seq:
            gene_allele["G group"] = f"'{gen_seq[allele]}'"
        else:
            gene_allele["G group"] = ''
        all_fields_present = True
        excluded_fields = ["G group", "MHC gene allele", "Subclass"]
        for field in gene_allele_fields:
            if field not in excluded_fields and field not in gene_allele.keys():
                all_fields_present = False
        if all_fields_present:
            gen_alleles.append(gene_allele)
        continue
    G_groups = [{"G group" : allele, "Exon 2 and/or 3": max(G_groups[allele], key=len), "Logic": "G group"} for allele in G_groups]
    gen_alleles = list(map(update_allele_dict, gen_alleles))
    return gen_alleles, G_groups, errors

def write_error_report(errors):
    with open("build/report-g-grp.json", "w") as report:
        json.dump(errors, report)

def write_gene_alleles(gene_allele_fields, gen_alleles):
    with open("ontology/gene-alleles.tsv", "w") as file_obj:

        writer = csv.DictWriter(file_obj, fieldnames = gene_allele_fields, delimiter = "\t")
        writer.writeheader()
        #file_obj.write("LABEL\tEC 'has gene product' some %\tEC 'has part' some %\tA MRO:accession\tA MRO:source\tA MRO:sequence\n")
        #writer.writerows([gen_alleles[0]])
        file_obj.write("LABEL\tEC 'has gene product' some %\tSC 'has part' some %\tSC %\tSC 'gene product of' some %\tA MRO:accession\tA MRO:source\tA MRO:sequence\n")
        writer.writerows(gen_alleles)
        file_obj.close()

def write_G_groups(G_groups):
    with open("ontology/G-group.tsv", "w") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames = ["G group", "Exon 2 and/or 3", "Logic"], delimiter = "\t")
        writer.writeheader()
        file_obj.write("LABEL\tA MRO:sequence\tSC %\n")
        writer.writerows([G_groups[0]])
        writer.writerows(G_groups)
        file_obj.close()

def update_index(gen_alleles, G_groups):
    index = open("index.tsv")

    entries = index.read().splitlines()
    index.close()
    first = entries[0]
    second = entries[1]
    entries = entries[2:]
    entries = list(map(lambda entry: dict(zip(["ID", "Label", "Type", "Depreciated?"], entry.split("\t"))), entries))
    ids = [int(entry["ID"].split(":")[1]) for entry in entries]
    cur_mro_id = max(ids) + 1
    labels = [entry["Label"] for entry in entries]

    new_alleles = [allele["MHC gene allele"] for allele in gen_alleles if allele["MHC gene allele"] not in labels]
    new_G_groups = [allele["G group"] for allele in G_groups if allele["G group"].replace("'", "") not in labels]
    with open("index.tsv", "a+") as index:
        if "G group" not in labels:
            entry = ["MRO:" + str(cur_mro_id).zfill(7), "G group", "owl:Class"]
            index.write("\t".join(entry))
            index.write("\n")
            cur_mro_id +=1
        if "MHC gene allele" not in labels:
            entry = ["MRO:" + str(cur_mro_id).zfill(7), "MHC gene allele", "owl:Class"]
            index.write("\t".join(entry))
            index.write("\n")
            cur_mro_id +=1
        if "generic G group" not in labels:
            entry = ["MRO:" + str(cur_mro_id).zfill(7), "generic G group", "owl:Class"]
            index.write("\t".join(entry))
            index.write("\n")
            cur_mro_id +=1
        for new_allele in new_alleles:
            entry = ["MRO:" + str(cur_mro_id).zfill(7), new_allele, "owl:Class"]
            cur_mro_id +=1
            index.write("\t".join(entry))
            index.write("\n")
        for g_group in new_G_groups:
            entry = ["MRO:" + str(cur_mro_id).zfill(7), g_group, "owl:Class"]
            cur_mro_id +=1
            index.write("\t".join(entry))
            index.write("\n")

def read_template_data():
    alleles_file = open("ontology/gene-alleles.tsv", "r")
    fields = next(alleles_file).replace("\n", "").split("\t")
    next(alleles_file)
    gene_alleles = csv.DictReader(alleles_file, fieldnames = fields, delimiter="\t")
    gene_alleles = [dict(row) for row in gene_alleles]
    return gene_alleles

def verify_data(data, gene_alleles):
    levels = list(map(list, zip(*data.columns)))
    primary = ""
    secondary = ""
    for i in levels[0]:
        if "Allele Summary" in i:
            primary = i
            break
    for i in levels[1]:
        if "AlleleID" in i:
            secondary = i
            break
        if "Allele ID" in i:
            secondary = i
            break
    print(primary)
    m = pd.DataFrame(data.loc[:,  (primary, secondary)].dropna(), copy = True)
    m.columns = m.columns.droplevel(0)
    m = m.rename(columns = {"AlleleID": "Accession"})
    missed_alleles = []
    correction = m.isin(gene_alleles)
    for i in correction.index:
        if not correction.loc[i].bool() and not i.endswith("N"):
            missed_alleles.append(i)

    print(missed_alleles)
    return missed_alleles


def main():
    parser = argparse.ArgumentParser(description='Update MHC gene allele sequences and G groups or add frequency data')
    parser.add_argument("-u","--update", action='store_true', help = "Update G groups and coding region genomic sequences of HLA alleles from IMGT")
    parser.add_argument("-f", "--frequency", action = 'store_true', help = "This will install pandas Python package and update the frequency of each HLA allele in IMGT in population groups with data from CIWD")
    args = parser.parse_args()
    if args.update:
        gen_seq = get_G_groups()
        chains = get_chains()
        gene_allele_fields = ["MHC gene allele", "Chain", "G group", "Subclass", "Locus","Accession","Source","Coding Region Sequence"]
        gen_alleles, G_groups, errors = process_hla_dat(gen_seq = gen_seq, gene_allele_fields = gene_allele_fields, chains = chains)
        write_error_report(errors)
        write_gene_alleles(gene_allele_fields = gene_allele_fields, gen_alleles = gen_alleles)
        write_G_groups(G_groups)
        update_index(gen_alleles= gen_alleles, G_groups = G_groups)
    if args.frequency:
        try:
            import pandas as pd
            import glob
            datafiles = glob.glob("build/HLA-*-frequency.xlsx")
            gene_alleles = read_template_data()
            gene_alleles = pd.DataFrame(gene_alleles)
            gene_alleles.loc[:, "MHC gene allele"] = gene_alleles.loc[:, "MHC gene allele"].str.replace(" gene allele", "").str.replace("HLA-", "")
            gene_alleles = gene_alleles.set_index("MHC gene allele")
            missed_alleles = []
            for datafile in datafiles:
                data = pd.read_excel(io = datafile, header = [0, 1], index_col = 0)
                missed_alleles = missed_alleles + verify_data(data, gene_alleles)
            print(len(missed_alleles))
        except ModuleNotFoundError:
            print("Please install pandas")


if __name__ == "__main__":
    main()


# file_obj = open("G-group.tsv", "w")
# writer = csv.DictWriter(file_obj, fieldnames = ["G group", "seqs", "subclass"], delimiter = "\t")
# writer.writeheader()
# writer.writerows(G_groups)
# file_obj.close()
