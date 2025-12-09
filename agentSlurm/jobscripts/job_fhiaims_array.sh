#!/bin/bash
#SBATCH -N 1
# #SBATCH --mem=1G
#SBATCH --ntasks-per-node=1
# #SBATCH --constraint="polonium|tellurium"
#SBATCH --constraint="polonium"
# #SBATCH --constraint="tellurium"
# #SBATCH --exclude=tellurium10,tellurium9
#SBATCH --array=0-9999%300

# Array job of multiple single processor calculations  
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

# Run parallel on single node
# mpirun -n 20 $BIN   | tee aims.out
# mpirun -n 20 $BIN > aims.out 2>&1

prefix=polar_step
idx=$(($n+$interval*$SLURM_ARRAY_TASK_ID))
calcdir=${prefix}_${idx}

# Print potential useful info
echo $HOSTNAME
echo ${calcdir}

cp control_polarizabilities.in ${calcdir}/control.in
cd ${calcdir}
#mpirun -n 2 $BIN >aims.out 2>&1
$BIN >aims.out 2>&1
rm control.in
