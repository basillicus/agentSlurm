#!/bin/bash
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --constraint="polonium"
#SBATCH --array=0-9999%300

#: Array job of multiple single processor calculations
n=0
interval=2

module use /usr/license/modulefiles

# module load intel   # Currently not working
# Workaround:
source /usr/license/intel/compiler/2023.1.0/env/vars.sh

module load mkl
module load impi

ulimit -s unlimited

FHI_PATH=/usr/license/fhi-aims/bin/
FHI_BIN=aims.231212.scalapack.mpi.x

BIN=${FHI_PATH}${FHI_BIN}

prefix=polar_step
idx=$(($n + $interval * $SLURM_ARRAY_TASK_ID))
calcdir=${prefix}_${idx}

# Print potential useful info
echo $HOSTNAME
echo ${calcdir}

cp control_polarizabilities.in ${calcdir}/control.in
cd ${calcdir}
#mpirun -n 2 $BIN >aims.out 2>&1
$BIN >aims.out 2>&1
rm control.in
