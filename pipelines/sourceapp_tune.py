#!/usr/bin/env python3
"""
SourceApp: Python implementation of the Unix-based environmental monitoring tool.
"""

import os
import sys
import math
import argparse
import subprocess
import pandas as pd

### Core functions:

def read_filter(args, limit_threshold, query_coverage, percent_identity):
    bam = args['sourceapp_outdir'] + '/mappings.bam'
    gdef = args['sourceapp_database'] + '/gdef.txt'
    pid=percent_identity
    qcov=query_coverage
    threads=args['threads']
    trunc=limit_threshold
    output = args['sourceapp_outdir'] + '/mappings_filtered.txt'

    usegeq=args['use_geq']
    print("Filtering read mapping results...")
    if trunc == 0: # if -l 0 or --no-limits was passed
        if usegeq:
            try:
                subprocess.run(["coverm genome -b "+bam+" --genome-definition "+gdef+" --min-read-percent-identity "+str(pid*100)+
                            " --min-read-aligned-percent "+str(qcov*100)+" --output-format dense -t "+str(threads)+" -m mean covered_bases variance "+
                            "-o "+output], shell=True, check=True)
            except Exception as e:
                print('Error in step 4: filtering of read mappings. Exiting . . .')
                sys.exit()
        else:
            try:
                subprocess.run(["coverm genome -b "+bam+" --genome-definition "+gdef+" --min-read-percent-identity "+str(pid*100)+
                            " --min-read-aligned-percent "+str(qcov*100)+" --output-format dense -t "+str(threads)+" -m relative_abundance "+
                            " -o "+output], shell=True, check=True)
            except Exception as e:
                print('Error in step 4: filtering of read mappings. Exiting . . .')
                sys.exit()
    else: # if -l is nonzero and --no-limits wasn't passed
        if usegeq:
            try:
                subprocess.run(["coverm genome -b "+bam+" --genome-definition "+gdef+" --min-read-percent-identity "+str(pid*100)+
                            " --min-read-aligned-percent "+str(qcov*100)+" --output-format dense -t "+str(threads)+" -m trimmed_mean covered_bases variance "+
                            " -o "+output+" --trim-min "+str(trunc*100)+" --trim-max "+str(100-(trunc*100))], shell=True, check=True)
            except Exception as e:
                print('Error in step 4: filtering of read mappings. Exiting . . .')
                sys.exit()
        else:
            try:
                subprocess.run(["coverm genome -b "+bam+" --genome-definition "+gdef+" --min-read-percent-identity "+str(pid*100)+
                            " --min-read-aligned-percent "+str(qcov*100)+" --output-format dense -t "+str(threads)+" -m relative_abundance "+
                            " -o "+output+" --trim-min "+str(trunc*100)+" --trim-max "+str(100-(trunc*100))], shell=True, check=True)
            except Exception as e:
                print('Error in step 4: filtering of read mappings. Exiting . . .')
                sys.exit()

def summarize(args):
    #produce the final dataframe and make some visuals.
    usegeq=args['use_geq']
    correctloq=args['correct_loq']
    sourcedict = pd.read_csv(args['sourceapp_database'].replace('/','') + '/sources.txt',sep="\t",header=0).iloc[:,0:2].set_index('genome')['source'].to_dict()
    sources = sorted(list(set(sourcedict.values())))
    df = pd.read_csv(args['sourceapp_outdir'] + '/mappings_filtered.txt', header=0, sep='\t')
    portions=[]
    if usegeq:
        geq = get_geq(args)
        for source in sources:
            gsum=0
            glist = [key for key, val in sourcedict.items() if val == source]
            for genome in glist:
                if df[df['Genome'] == genome].iloc[:,1].sum() >= -1*math.log(0.9): # above LOQ
                    gsum = gsum + df[df['Genome']==genome].iloc[:,1].sum()
                elif df[df['Genome'] == genome].iloc[:,1].sum() < -1*math.log(0.9) and df[df['Genome'] == genome].iloc[:,1].sum() > 0: # below LOQ above LOD
                    if correctloq: # if we 
                        gsum = gsum + -1*math.log(0.9)
                    else:
                        gsum = gsum + df[df['Genome']==genome].iloc[:,1].sum()
            geq_frac = gsum/geq
            portions.append([source,geq_frac])
        portions = pd.DataFrame(portions, columns=['Source','Portion'])
        if portions['Portion'].sum() > 1:
            portions['Portion'] = portions['Portion']/portions['Portion'].sum()
            print('Warning: the sum of GEQ-based relative abundances exceeds 1. Source portions have been rescaled.')
            print('It is recommended to re-run SourceApp without the --use-geq flag to examine what percentage of reads are recovered. If the value is <~90%, then GEQ-based normalization may not be robust for this dataset.')
    else:
        for source in sources: # if we don't normalize to GEQ, then we should just report DNA relabd.
            gsum=0
            glist = [key for key, val in sourcedict.items() if val == source]
            for genome in glist:
                gsum = gsum + df[df['Genome']==genome].iloc[:,1].sum()
            portions.append([source,gsum])
        portions = pd.DataFrame(portions, columns=['Source', 'Portion'])
    return (portions/100)

### Helper functions:
def get_geq(args):
    file = args['sourceapp_outdir'] + '/geq.txt'
    with open(file) as fh:
        for index, line in enumerate(fh):
            if index == 12:
                censusline = line.split()
    output = float(censusline[1])
    return output

### Pipeline:
def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
        )
    parser.add_argument(
        '-i', '--sourceapp-outdir',
        help='Path to output directory of a SourceApp.py run',
        metavar='',
        type=str,
        required=True
        )
    parser.add_argument(
        '-o', '--out-file',
        help='Path to desired output file (SourceApp will append ".tune.csv")',
        metavar='',
        type=str,
        required=True
        )
    parser.add_argument(
        '-d', '--sourceapp-database',
        help='Path to directory containing a SourceApp formatted database. Default database available for download or produced de novo as the output directory from sourceapp_build.py',
        metavar='',
        type=str,
        required=True
        )
    parser.add_argument(
        '-t','--threads',
        help='Threads available to SourceApp',
        metavar='',
        type=int,
        default=1,
        required=False
        )
    parser.add_argument(
        '--use-geq',
        help='Report results normalized to genome equivalents -- only pass this flag if your original SourceApp run contained it.',
        action='store_true',
        required=False
        )
    parser.add_argument(
        '--correct-loq',
        help='Use quantification threshold to correct truncation estimation (if not used, the value reported will be accepted, even though its known to be an underestimate; this is a rare event)',
        action='store_true',
        required=False
        )
    args=vars(parser.parse_args())

    print("Beginning SourceApp tune", flush=True)
    
    if args['sourceapp_outdir'][-1] == '/': # in the event user provides trailing '/'
        args['sourceapp_outdir'] = args['sourceapp_outdir'][:-1]

    if args['sourceapp_database'][-1] == '/': # in the event user provides trailing '/'
        args['sourceapp_database'] = args['sourceapp_database'][:-1]
        
                #TAD100, TAD98,TAD90,TAD80,TAD70
    limit_threshold = [0, 0.01, 0.05, 0.1, 0.15] # 5
    query_coverage = [0.3,0.5,0.7,0.9] # 4
    percent_identity = [0.89,0.91,0.93,0.95,0.97,0.99] # 6
    # n = 4*5*6 = 96 runs/ea

    i=0
    for l in limit_threshold:
        for q in query_coverage:
            for p in percent_identity:
                read_filter(args, l, q, p)
                results = summarize(args)
                if i == 0:
                    total_out = pd.DataFrame()
                    col1 = results['Source']
                    col1.loc[len(col1)] = 'limit_threshold'
                    col1.loc[len(col1)] = 'query_coverage'
                    col1.loc[len(col1)] = 'percent_identity'
                    total_out['Source'] = col1
                col2=results['Portion']
                col2.loc[len(col2)]=l
                col2.loc[len(col2)]=q
                col2.loc[len(col2)]=p
                total_out['iteration '+str(i+1)] = col2
                i = i + 1
                print(i, " / 96 iterations finished", flush=True)
    
    print(total_out, flush=True)
    total_out.to_csv(args['out_file']+'.tune.csv',index=False)
                
if __name__ == "__main__":
    main()
