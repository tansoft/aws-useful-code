#!/usr/bin/env python3
"""Script to grab GPU instances via On-Demand, EC2 Capacity Blocks, or SageMaker Training Plans."""

import argparse
import json
import time
import sys
from datetime import datetime, timedelta, timezone
import boto3
from botocore.exceptions import ClientError


# ── Shared helpers ──────────────────────────────────────────────────────────

def get_all_azs(ec2):
    """Get all available AZs as list of (az_name, az_id)."""
    resp = ec2.describe_availability_zones(
        Filters=[{"Name": "state", "Values": ["available"]}]
    )
    return [(z["ZoneName"], z["ZoneId"]) for z in resp["AvailabilityZones"]]


def resolve_azs(ec2, az_name_or_id=None):
    """Resolve to list of (az_name, az_id). If az is None, return all AZs."""
    all_azs = get_all_azs(ec2)
    if not az_name_or_id:
        return all_azs
    for z in all_azs:
        if az_name_or_id in z:
            return [z]
    return []


def find_subnet_in_az(ec2, az_name):
    """Find a subnet in the given AZ."""
    resp = ec2.describe_subnets(
        Filters=[{"Name": "availability-zone", "Values": [az_name]}]
    )
    return resp["Subnets"][0]["SubnetId"] if resp["Subnets"] else None


def get_latest_ami(ec2):
    """Get latest Amazon Linux 2023 AMI."""
    resp = ec2.describe_images(
        Owners=["amazon"],
        Filters=[
            {"Name": "name", "Values": ["al2023-ami-2023.*-kernel-*-x86_64"]},
            {"Name": "state", "Values": ["available"]},
            {"Name": "architecture", "Values": ["x86_64"]},
        ],
    )
    images = sorted(resp["Images"], key=lambda x: x["CreationDate"], reverse=True)
    return images[0]["ImageId"] if images else None


# ── Mode 1: On-Demand (retry loop) ─────────────────────────────────────────

def run_ondemand(args):
    ec2 = boto3.client("ec2", region_name=args.region)
    azs = resolve_azs(ec2, args.az)
    if not azs:
        sys.exit(f"ERROR: Cannot resolve AZ '{args.az}' in region {args.region}")
    print(f"AZs: {', '.join(f'{n} ({i})' for n, i in azs)}")

    ami_id = args.ami or get_latest_ami(ec2)
    if not ami_id:
        sys.exit("ERROR: Cannot find AMI. Specify --ami manually.")
    print(f"AMI: {ami_id}")

    attempt = 0
    while True:
        for az_name, az_id in azs:
            attempt += 1
            subnet_id = args.subnet or find_subnet_in_az(ec2, az_name)
            try:
                print(f"\n[Attempt {attempt}] Requesting {args.instance_type} in {az_name}...")
                params = {
                    "ImageId": ami_id,
                    "InstanceType": args.instance_type,
                    "MinCount": 1, "MaxCount": 1,
                    "Placement": {"AvailabilityZone": az_name},
                    "DryRun": args.dry_run,
                    "TagSpecifications": [{"ResourceType": "instance",
                                           "Tags": [{"Key": "Name", "Value": f"{args.instance_type}-{az_name}"}]}],
                }
                if subnet_id:
                    params["SubnetId"] = subnet_id
                if args.key_name:
                    params["KeyName"] = args.key_name
                resp = ec2.run_instances(**params)
                print(f"SUCCESS! Instance: {resp['Instances'][0]['InstanceId']}")
                return
            except ClientError as e:
                code = e.response["Error"]["Code"]
                msg = e.response["Error"]["Message"]
                if code == "DryRunOperation":
                    print("Dry run succeeded - request would have been accepted.")
                    return
                elif code in ("InsufficientInstanceCapacity", "InstanceLimitExceeded", "Unsupported"):
                    print(f"  {code}: {msg}")
                else:
                    sys.exit(f"  ERROR [{code}]: {msg}")

            if args.max_retries and attempt >= args.max_retries:
                sys.exit(f"\nMax retries ({args.max_retries}) reached.")

        print(f"  Retrying all AZs in {args.interval}s...")
        time.sleep(args.interval)


# ── Mode 2: EC2 Capacity Blocks ────────────────────────────────────────────

def run_capacity_block(args):
    ec2 = boto3.client("ec2", region_name=args.region)
    azs = resolve_azs(ec2, args.az)
    if not azs:
        sys.exit(f"ERROR: Cannot resolve AZ '{args.az}' in region {args.region}")
    az_names = {n for n, _ in azs}
    print(f"AZs: {', '.join(f'{n} ({i})' for n, i in azs)}")

    instance_count = args.instance_count
    duration_hours = args.duration_hours
    now = datetime.now(timezone.utc)

    # Search for offerings
    search_params = {
        "InstanceType": args.instance_type,
        "InstanceCount": instance_count,
        "CapacityDurationHours": duration_hours,
        "StartDateRange": now,
        "EndDateRange": now + timedelta(days=7),
    }

    print(f"\nSearching Capacity Block offerings: {instance_count}x {args.instance_type}, {duration_hours}h...")
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = ec2.describe_capacity_block_offerings(**search_params)
            offerings = resp.get("CapacityBlockOfferings", [])

            # Filter by AZ(s)
            offerings = [o for o in offerings if o["AvailabilityZone"] in az_names]

            if not offerings:
                print(f"  [Attempt {attempt}] No offerings in {', '.join(az_names)}.")
                if args.max_retries and attempt >= args.max_retries:
                    sys.exit(f"\nMax retries ({args.max_retries}) reached.")
                print(f"  Retrying in {args.interval}s...")
                time.sleep(args.interval)
                continue

            # Show offerings
            print(f"\nFound {len(offerings)} offering(s):")
            for i, o in enumerate(offerings):
                print(f"  [{i}] ID: {o['CapacityBlockOfferingId']}")
                print(f"      AZ: {o['AvailabilityZone']}, Instances: {o['InstanceCount']}")
                print(f"      Start: {o['StartDate']}, End: {o['EndDate']}")
                print(f"      Duration: {o.get('CapacityBlockDurationHours', '?')}h, Fee: ${o.get('UpfrontFee', '?')} {o.get('CurrencyCode', '')}")

            if args.dry_run:
                print("\nDry run - not purchasing.")
                return

            # Auto-purchase first (cheapest/earliest) offering
            if args.auto_purchase:
                chosen = offerings[0]
            else:
                idx = input(f"\nSelect offering [0-{len(offerings)-1}] or 'q' to quit: ").strip()
                if idx.lower() == "q":
                    return
                chosen = offerings[int(idx)]

            offering_id = chosen["CapacityBlockOfferingId"]
            cb_az = chosen["AvailabilityZone"]
            print(f"\nPurchasing Capacity Block {offering_id}...")
            purchase_resp = ec2.purchase_capacity_block(
                CapacityBlockOfferingId=offering_id,
                InstancePlatform="Linux/UNIX",
                TagSpecifications=[{"ResourceType": "capacity-block",
                                    "Tags": [{"Key": "Name", "Value": f"cb-{args.instance_type}-{cb_az}"}]}],
            )
            cb = purchase_resp.get("CapacityBlock", purchase_resp)
            print(f"SUCCESS! Capacity Block purchased.")
            print(f"  ID: {cb.get('CapacityBlockId', 'N/A')}")
            print(f"  State: {cb.get('State', 'N/A')}")
            return

        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            print(f"  ERROR [{code}]: {msg}")
            if code not in ("InsufficientInstanceCapacity", "Unavailable"):
                sys.exit(1)
            if args.max_retries and attempt >= args.max_retries:
                sys.exit(f"\nMax retries ({args.max_retries}) reached.")
            print(f"  Retrying in {args.interval}s...")
            time.sleep(args.interval)


# ── Mode 3: SageMaker Training Plans ───────────────────────────────────────

def run_training_plan(args):
    sm = boto3.client("sagemaker", region_name=args.region)

    instance_count = args.instance_count
    duration_hours = args.duration_hours
    target = args.sm_target  # "training-job" or "hyperpod-cluster"
    now = datetime.now(timezone.utc)

    sm_instance_type = args.instance_type if args.instance_type.startswith("ml.") else f"ml.{args.instance_type}"

    search_params = {
        "InstanceType": sm_instance_type,
        "InstanceCount": instance_count,
        "DurationHours": duration_hours,
        "TargetResources": [target],
        "StartTimeAfter": now,
        "EndTimeBefore": now + timedelta(weeks=8),
    }

    print(f"\nSearching SageMaker Training Plan offerings: {instance_count}x {sm_instance_type}, {duration_hours}h, target={target}...")
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = sm.search_training_plan_offerings(**search_params)
            offerings = resp.get("TrainingPlanOfferings", [])

            if not offerings:
                print(f"  [Attempt {attempt}] No offerings available.")
                if args.max_retries and attempt >= args.max_retries:
                    sys.exit(f"\nMax retries ({args.max_retries}) reached.")
                print(f"  Retrying in {args.interval}s...")
                time.sleep(args.interval)
                continue

            # Show offerings
            print(f"\nFound {len(offerings)} offering(s):")
            for i, o in enumerate(offerings):
                print(f"  [{i}] ID: {o['TrainingPlanOfferingId']}")
                print(f"      Duration: {o.get('DurationHours', '?')}h, Fee: ${o.get('UpfrontFee', '?')} {o.get('CurrencyCode', '')}")
                print(f"      Target: {o.get('TargetResources', [])}")
                for rc in o.get("ReservedCapacityOfferings", []):
                    print(f"      -> {rc.get('InstanceType')} x{rc.get('InstanceCount')} in {rc.get('AvailabilityZone', 'N/A')}, "
                          f"{rc.get('DurationHours', '?')}h, start={rc.get('StartDate', 'N/A')}")

            if args.dry_run:
                print("\nDry run - not purchasing.")
                return

            # Auto-purchase first offering
            if args.auto_purchase:
                chosen = offerings[0]
            else:
                idx = input(f"\nSelect offering [0-{len(offerings)-1}] or 'q' to quit: ").strip()
                if idx.lower() == "q":
                    return
                chosen = offerings[int(idx)]

            offering_id = chosen["TrainingPlanOfferingId"]
            plan_name = args.plan_name or f"{args.instance_type}-plan-{int(now.timestamp())}"
            print(f"\nCreating Training Plan '{plan_name}' from offering {offering_id}...")
            create_resp = sm.create_training_plan(
                TrainingPlanName=plan_name,
                TrainingPlanOfferingId=offering_id,
            )
            print(f"SUCCESS! Training Plan created.")
            print(f"  ARN: {create_resp['TrainingPlanArn']}")
            return

        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            print(f"  ERROR [{code}]: {msg}")
            if code not in ("ResourceLimitExceeded",):
                sys.exit(1)
            if args.max_retries and attempt >= args.max_retries:
                sys.exit(f"\nMax retries ({args.max_retries}) reached.")
            print(f"  Retrying in {args.interval}s...")
            time.sleep(args.interval)


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Grab GPU instances via On-Demand, Capacity Blocks, or SageMaker Training Plans",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # On-Demand retry loop (default p5.4xlarge)
  %(prog)s ondemand --region us-east-1 --az use1-az5

  # On-Demand with custom instance type, all AZs
  %(prog)s ondemand --region us-east-1 --instance-type p5e.48xlarge

  # Search & purchase EC2 Capacity Block
  %(prog)s capacity-block --region us-east-1 --az use1-az5 --duration 24

  # Search & purchase SageMaker Training Plan
  %(prog)s training-plan --region us-east-1 --instance-type p5.48xlarge --duration 48 --sm-target training-job
""",
    )
    # Common args
    parser.add_argument("--region", required=True, help="AWS region")
    parser.add_argument("--az", default=None, help="AZ name or ID (e.g. us-east-1e or use1-az5). If omitted, tries all AZs")
    parser.add_argument("--instance-type", default="p5.4xlarge", help="EC2 instance type (default: p5.4xlarge)")
    parser.add_argument("--interval", type=int, default=10, help="Retry interval seconds (default: 10)")
    parser.add_argument("--max-retries", type=int, default=0, help="Max retries, 0=unlimited")
    parser.add_argument("--dry-run", action="store_true", help="Dry run / search only")

    sub = parser.add_subparsers(dest="mode", required=True)

    # On-Demand
    p_od = sub.add_parser("ondemand", help="On-Demand instance with retry loop")
    p_od.add_argument("--ami", help="AMI ID (auto-detect if omitted)")
    p_od.add_argument("--subnet", help="Subnet ID (auto-detect if omitted)")
    p_od.add_argument("--key-name", help="EC2 key pair name")

    # Capacity Block
    p_cb = sub.add_parser("capacity-block", help="EC2 Capacity Block reservation")
    p_cb.add_argument("--instance-count", type=int, default=1, help="Number of instances (default: 1)")
    p_cb.add_argument("--duration", type=int, default=24, dest="duration_hours", help="Duration in hours (default: 24)")
    p_cb.add_argument("--auto-purchase", action="store_true", help="Auto-purchase first available offering")

    # SageMaker Training Plan
    p_tp = sub.add_parser("training-plan", help="SageMaker Training Plan reservation")
    p_tp.add_argument("--instance-count", type=int, default=1, help="Number of instances (default: 1)")
    p_tp.add_argument("--duration", type=int, default=24, dest="duration_hours", help="Duration in hours (default: 24)")
    p_tp.add_argument("--sm-target", choices=["training-job", "hyperpod-cluster"], default="training-job",
                       help="Target resource type (default: training-job)")
    p_tp.add_argument("--plan-name", help="Training plan name (auto-generated if omitted)")
    p_tp.add_argument("--auto-purchase", action="store_true", help="Auto-purchase first available offering")

    args = parser.parse_args()

    if args.mode == "ondemand":
        run_ondemand(args)
    elif args.mode == "capacity-block":
        run_capacity_block(args)
    elif args.mode == "training-plan":
        run_training_plan(args)


if __name__ == "__main__":
    main()