#!/usr/bin/env python

# Run rspr

import sys
import os
import argparse
import subprocess
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import seaborn as sns
from pathlib import Path


#####################################################################
### FUNCTION PARSE_ARGS
### Parse the command-line arguments.
### args: the arguments
### RETURN a list that contains values for all the defined arguments.
#####################################################################


def parse_args(args=None):
    Description = "Run rspr"
    Epilog = "Example usage: rspr.py INPUT_DIR_PATH"
    parser = argparse.ArgumentParser(description=Description, epilog=Epilog)
    parser.add_argument(
        "-df", "--dataframe", dest="SUBSET_DF", help="CSV table subset by group"
    )
    parser.add_argument(
        "-mar",
        "--max_approx_rspr",
        dest="MAX_APPROX_RSPR_DIST",
        type=int,
        default=-1,
        help="Maximum approximate rSPR distance",
    )
    parser.add_argument(
        "-mbl",
        "--min_branch_length",
        dest="MIN_BRANCH_LENGTH",
        type=int,
        default=0,
        help="Minimum branch length",
    )
    parser.add_argument(
        "-mst",
        "--max_support_threshold",
        dest="MAX_SUPPORT_THRESHOLD",
        type=float,
        default=0.7,
        help="Maximum support threshold",
    )
    return parser.parse_args(args)


#####################################################################
### FUNCTION EXTRACT_EXACT_DISTANCE
### Extract exact rspr distance from the rspr output
### text: rspr output text
### RETURN exact rspr distance
#####################################################################


def extract_exact_distance(text):
    for line in text.splitlines():
        if "total exact drSPR=" in line:
            distance = line.split("total exact drSPR=")[1].strip()
            return distance
    return "0"

def create_scatter(center, num_points):
    r = 1
    return [(center + r * np.cos(2 * np.pi / num_points * x), center + r * np.sin(2 * np.pi / num_points * x)) for x in range(num_points)]

def generate_cluster_diagram(clusters, cluster_path):
    fig, ax = plt.subplots()
    
    cluster_idx = 1
    center_val = 0
    for cluster in clusters:
        center_val += 5
        x, y = zip(*create_scatter(center_val, len(cluster)))
        ax.scatter(x, y, label=f'Cluster {cluster_idx}')
        cluster_idx += 1

        for i, label in enumerate(cluster):
            ax.annotate(label, (x[i], y[i]), textcoords="offset points", xytext=(5,5), ha='center')

    ax.legend(loc='upper left')
    ax.set_title('Clusters Representation')
    plt.savefig(cluster_path)


#####################################################################
### FUNCTION FPT_RSPR
### Run exact rspr algorithm of set of input tree pairs
### results_df: dataframe to input tree pairs and store the exact rspr results
### min_branch_len: minimum branch length
### max_support_threshold: maximum branching support threshold
#####################################################################

def fpt_rspr(results_df, folder_path, min_branch_len=0, max_support_threshold=0.7, gather_cluster_info=True):
    print("Calculating exact distance")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(current_dir, 'rspr.exe')
    rspr_path = [
        exe_path,
        "-multifurcating",
        "-show_clusters",
        "-length " + str(min_branch_len),
        "-support " + str(max_support_threshold),
    ]

    trees_path = os.path.join(folder_path, "rooted_gene_trees")
    cluster_path = os.path.join(folder_path, "cluster_diagrams")
    Path(cluster_path).mkdir(exist_ok=True)

    # Run this groups in parallel
    for filename in results_df.index:
        gene_tree_path = os.path.join(trees_path, filename)
        full_output = ""
        with open(gene_tree_path, "r") as infile:
            if not gather_cluster_info:
            # Clustering information not required
                result = subprocess.run(
                    rspr_path, stdin=infile, capture_output=True, text=True
                )
                full_output = result.stdout
            else:
            # Clustering information required
                process = subprocess.Popen(
                    rspr_path, stdin=infile, stdout=subprocess.PIPE, text=True, universal_newlines=True
                )

                clusters = []
                cluster_diagram_path = os.path.join(cluster_path, filename + ".png")
                clustering_start = False
                output_lines = []
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    if "Clusters start" in line:
                        clustering_start = True
                        continue
                    elif "Clusters end" in line:
                        clustering_start = False
                    
                    if clustering_start:
                        updated_line = line.replace('(', '').replace(')', '').replace('\n', '')
                        cluster_nodes = updated_line.split(',')
                        cluster_nodes = [int(node) for node in cluster_nodes if "X" not in node]
                        clusters.append(cluster_nodes)
                    
                    output_lines.append(line)
                generate_cluster_diagram(clusters, cluster_diagram_path)
                process.wait()
                full_output = ''.join(output_lines)

            dist = extract_exact_distance(full_output)
            results_df.loc[filename, "exact_drSPR"] = dist

def main(args=None):
    args = parse_args(args)

    # Exact RSPR
    csv_path = os.path.join(args.SUBSET_DF, "output.tsv")
    results = pd.read_csv(csv_path, delimiter='\t')
    if args.MAX_APPROX_RSPR_DIST >= 0:
        results = results[(results["approx_drSPR"] <= args.MAX_APPROX_RSPR_DIST)]

    results.set_index("file_name", inplace=True)
    fpt_rspr(results, args.SUBSET_DF, args.MIN_BRANCH_LENGTH, args.MAX_SUPPORT_THRESHOLD)

    group = results["group_name"].unique()[0]
    res_path = f"exact_output_{group}.tsv"
    out_path = os.path.join(args.SUBSET_DF, res_path)
    results.fillna(value="NULL").to_csv(out_path, sep="\t", index=True)

    # From CSV
    """
    phylo_dir = os.path.join(args.INPUT_DIR_PATH, "phylogenomics")
    res_path = os.path.join(phylo_dir, 'exact_output.csv')
    fig_path = os.path.join(phylo_dir, 'exact_output.png')
    make_heatmap_from_csv(res_path, fig_path)
    """


if __name__ == "__main__":
    sys.exit(main())
