#!/bin/bash
#SBATCH --job-name=p2oldqueueclean
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=512M
#SBATCH --time=00:02:00
scancel 70133 70134 70135
echo "Obsolete pending historical/census jobs cancelled; replacement historical controls are running under 70155."
