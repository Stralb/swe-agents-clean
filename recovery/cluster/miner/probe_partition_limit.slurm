#!/bin/bash
#SBATCH --job-name=probe-limit
#SBATCH --time=00:10:00
#SBATCH --output=/home-mscluster/%u/probe_limit_%A_%a.log

echo "JOB=$SLURM_JOB_ID ARRAY=$SLURM_ARRAY_TASK_ID"
echo "PARTITION=$SLURM_JOB_PARTITION"
echo "HOST=$(hostname)"
echo "START=$(date)"
sleep 600
echo "END=$(date)"
