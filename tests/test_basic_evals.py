#!/usr/bin/env python3
"""
Basic EVALS harness for the Agentic Slurm Analyzer MVP.
"""

import sys
from pathlib import Path
from agentSlurm.pipeline_controller import PipelineController
from agentSlurm.models.job_context import UserProfile, Finding

# Add the project root to the path so we can import modules
# sys.path.insert(0, str(Path(__file__).parent))


def run_basic_evals():
    """
    Run basic evaluation tests on sample scripts.
    """
    print("Running basic EVALS for AgentSlurm MVP...")
    print("=" * 50)

    # Test case 1: Script with missing lfs setstripe for large files
    print("\nTest 1: Script with large-file tools but no lfs setstripe")
    print("-" * 55)

    test_script_1 = """#!/bin/bash
#SBATCH --job-name=test_job
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=16
#SBATCH --time=02:00:00
#SBATCH --output=output.log

# Load modules
module load bwa/0.7.17
module load samtools/1.16.1

# Run alignment
bwa mem -t 16 reference.fa reads.fastq > aligned.sam
samtools sort -@ 16 aligned.sam -o aligned.sorted.bam

# Index
samtools index aligned.sorted.bam
"""

    controller = PipelineController(user_profile=UserProfile.MEDIUM)
    context_1 = controller.run_pipeline(test_script_1, "test_script_1.sh")

    print("Analysis report:")
    print(context_1.responses[0]["content"])

    # Check if the expected finding (LUSTRE-001) was detected
    lustre_001_findings = [f for f in context_1.findings if f.rule_id == "LUSTRE-001"]
    if lustre_001_findings:
        print(
            f"\n✅ PASS: LUSTRE-001 rule correctly detected (found {len(lustre_001_findings)} finding(s))"
        )
    else:
        print(f"\n❌ FAIL: LUSTRE-001 rule not detected")

    # Test case 2: Script with small-file tools and wide striping (should trigger LUSTRE-002)
    print("\n" + "=" * 50)
    print("\nTest 2: Script with small-file tools and wide striping")
    print("-" * 55)

    test_script_2 = """#!/bin/bash
#SBATCH --job-name=test_job
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --time=01:00:00
#SBATCH --output=output.log

# Set wide striping (this should trigger a warning for small files)
lfs setstripe -c 8 /tmp/output_dir

# Run QC tools (these create many small files)
fastqc -o /tmp/output_dir sample1.fastq sample2.fastq
multiqc -o /tmp/output_dir /tmp/output_dir

echo "QC complete"
"""

    context_2 = controller.run_pipeline(test_script_2, "test_script_2.sh")

    print("Analysis report:")
    print(context_2.responses[0]["content"])

    # Check if the expected finding (LUSTRE-002) was detected
    lustre_002_findings = [f for f in context_2.findings if f.rule_id == "LUSTRE-002"]
    if lustre_002_findings:
        print(
            f"\n✅ PASS: LUSTRE-002 rule correctly detected (found {len(lustre_002_findings)} finding(s))"
        )
    else:
        print(f"\n❌ FAIL: LUSTRE-002 rule not detected")

    # Test case 3: Script with proper striping for large files (should have no Lustre issues)
    print("\n" + "=" * 50)
    print("\nTest 3: Script with large-file tools and proper striping")
    print("-" * 55)

    test_script_3 = """#!/bin/bash
#SBATCH --job-name=test_job
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=16
#SBATCH --time=02:00:00
#SBATCH --output=output.log

# Set appropriate striping for large files
lfs setstripe -c 4 -s 64M /tmp/output_dir

# Load modules
module load bwa/0.7.17
module load samtools/1.16.1

# Run alignment
bwa mem -t 16 reference.fa reads.fastq > aligned.sam
samtools sort -@ 16 aligned.sam -o aligned.sorted.bam

# Index
samtools index aligned.sorted.bam
"""

    context_3 = controller.run_pipeline(test_script_3, "test_script_3.sh")

    print("Analysis report:")
    print(context_3.responses[0]["content"])

    # Check that no Lustre issues were detected
    lustre_findings = [f for f in context_3.findings if f.rule_id.startswith("LUSTRE-")]
    if not lustre_findings:
        print(f"\n✅ PASS: No Lustre issues detected (as expected)")
    else:
        print(
            f"\n❌ FAIL: Unexpected Lustre findings detected: {[f.rule_id for f in lustre_findings]}"
        )

    # Summary
    print("\n" + "=" * 50)
    print("EVALS SUMMARY")
    print("=" * 50)

    results = {
        "test_1_lustre_001": len(lustre_001_findings) > 0,
        "test_2_lustre_002": len(lustre_002_findings) > 0,
        "test_3_no_lustre_issues": len(lustre_findings) == 0,
    }

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())
    print(
        f"\nOverall result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}"
    )

    return all_passed


if __name__ == "__main__":
    run_basic_evals()

