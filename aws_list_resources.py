#!/usr/bin/env python3

import argparse
import boto3
import botocore.config
import botocore.exceptions
import concurrent.futures
import datetime
import fnmatch
import importlib.metadata
import json
import os
import packaging.version
import pathlib
import sys


AWS_DEFAULT_REGION = "us-east-1"

BOTO_CLIENT_CONFIG = botocore.config.Config(
    retries={"total_max_attempts": 5, "mode": "standard"},
    user_agent_appid="aws-list-resources",
)

TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"


class DeniedListOperationException(Exception):
    """
    Raised when the "List" operation of the Cloud Control API failed due to permission errors.
    """

    pass


def get_supported_resource_types(cloudformation_client):
    """
    Returns a list of resource types that are supported in a region by querying the CloudFormation registry.
    Examples: AWS::EC2::RouteTable, AWS::IAM::Role, AWS::KMS::Key, etc.
    """
    resource_types = set()
    list_types_paginator = cloudformation_client.get_paginator("list_types")
    for provisioning_type in ("FULLY_MUTABLE", "IMMUTABLE"):
        for list_types_page in list_types_paginator.paginate(
            Type="RESOURCE",
            Visibility="PUBLIC",
            ProvisioningType=provisioning_type,
            DeprecatedStatus="LIVE",
            Filters={"Category": "AWS_TYPES"},
        ):
            for type in list_types_page["TypeSummaries"]:
                resource_types.add(type["TypeName"])

    return list(resource_types)


def get_resources(cloudcontrol_client, resource_type):
    """
    Returns a list of discovered resources of the given resource type. Uses the "List" operation of the Cloud Control
    API. If the API call failed, an empty list is returned. If the API call likely failed because of permission
    issues, a DeniedListOperationException is raised.
    """
    collected_resources = []
    list_resources_paginator = cloudcontrol_client.get_paginator("list_resources")
    try:
        for list_resources_page in list_resources_paginator.paginate(TypeName=resource_type):
            for resource in list_resources_page["ResourceDescriptions"]:
                collected_resources.append(resource["Identifier"])

    except Exception as ex:
        # There is unfortunately a long and non-uniform list of exceptions that can occur with the Cloud Control API,
        # presumably because it just passes through the exceptions of the underlying services. Examples for when the
        # "List" operation requires additional parameters or when the caller lacks permissions for an API call:
        # UnsupportedActionException, InvalidRequestException, GeneralServiceException, ResourceNotFoundException,
        # HandlerInternalFailureException, AccessDeniedException, AuthorizationError, etc. They are thus handled by
        # this broad except clause. The end result is the same: resources for this resource type cannot be listed.
        exception_msg = str(ex).lower()
        for keyword in ("denied", "authorization", "authorized"):
            if keyword in exception_msg:
                raise DeniedListOperationException()

    return collected_resources


def log_error(msg, region):
    result_collection["_metadata"]["errors"][region].append(msg)
    print("Error: {}".format(msg))


def analyze_region(region):
    """
    Gets all resource types that are supported in the given region, lists their respective resources (if not filtered
    by arguments) and adds them to the result collection.
    """
    boto_session = boto3.Session(profile_name=args.profile, region_name=region)

    print("Reading supported resource types for region {}".format(region))
    cloudformation_client = boto_session.client("cloudformation", config=BOTO_CLIENT_CONFIG)
    try:
        resource_types_supported = get_supported_resource_types(cloudformation_client)
    except Exception as ex:
        msg = "Unable to list supported resource types for region {}: {}".format(region, str(ex))
        log_error(msg, region)
        return

    # Log if there are resource type arguments that don't have any matches in this region
    for pattern in sorted(set(args.include_resource_types + args.exclude_resource_types)):
        if not fnmatch.filter(resource_types_supported, pattern):
            msg = "Provided resource type does not match any supported resource types in region {}: {}".format(
                region, pattern
            )
            log_error(msg, region)

    # Filter resource types by include and exclude arguments
    resource_types_enabled = set()
    for pattern in args.include_resource_types:
        resource_types_enabled.update(fnmatch.filter(resource_types_supported, pattern))
    for pattern in args.exclude_resource_types:
        resource_types_enabled.difference_update(fnmatch.filter(resource_types_supported, pattern))
    resource_types_enabled = sorted(resource_types_enabled)

    # List resources for each enabled resource type
    cloudcontrol_client = boto_session.client("cloudcontrol", config=BOTO_CLIENT_CONFIG)
    for resource_type in resource_types_enabled:
        try:
            print("Listing {}, region {}".format(resource_type, region))
            resources = get_resources(cloudcontrol_client, resource_type)
            if resources:
                if args.only_show_counts:
                    result_collection["regions"][region][resource_type] = len(resources)
                else:
                    result_collection["regions"][region][resource_type] = sorted(resources)

        except DeniedListOperationException:
            msg = "Access denied to list resource type in region {}: {}".format(region, resource_type)
            log_error(msg, region)


def parse_resource_types(val):
    """
    Argument parser.
    """
    if not val:
        return []
    for resource_type in val.split(","):
        if not resource_type:
            raise argparse.ArgumentTypeError("Invalid resource type specification")
    return val.split(",")


def parse_regions(val):
    """
    Argument parser.
    """
    if val == "ALL":
        return val
    for region in val.split(","):
        if not region or region == "ALL":
            raise argparse.ArgumentTypeError("Invalid region specification")
    return sorted(set(val.split(",")))


if __name__ == "__main__":
    # Check runtime environment
    if sys.version_info < (3, 10):
        print("Python version 3.10 or higher required")
        sys.exit(1)
    with open(os.path.join(pathlib.Path(__file__).parent, "requirements.txt"), "r") as requirements_file:
        for package_requirement in requirements_file.read().splitlines():
            package_name, package_version = [val.strip() for val in package_requirement.split(">=")]
            installed_version = packaging.version.parse(importlib.metadata.version(package_name))
            expected_version = packaging.version.parse(package_version)
            if installed_version < expected_version:
                print("Unfulfilled requirement: {}".format(package_requirement))
                sys.exit(1)

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exclude-resource-types",
        default="",
        type=parse_resource_types,
        help="do not list the specified comma-separated resource types (supports wildcards)",
    )
    parser.add_argument(
        "--include-resource-types",
        default="*",
        type=parse_resource_types,
        help="only list the specified comma-separated resource types (supports wildcards)",
    )
    parser.add_argument(
        "--only-show-counts",
        default=False,
        action="store_true",
        help="only show resource counts instead of listing their full identifiers",
    )
    parser.add_argument(
        "--profile",
        help="named AWS profile to use when running the command",
    )
    parser.add_argument(
        "--regions",
        required=True,
        type=parse_regions,
        help="comma-separated list of target AWS regions or 'ALL'",
    )
    args = parser.parse_args()

    # Test for valid credentials
    try:
        boto_session = boto3.Session(profile_name=args.profile, region_name=AWS_DEFAULT_REGION)
    except botocore.exceptions.ProfileNotFound as ex:
        print("Error: {}".format(ex))
        sys.exit(1)
    sts_client = boto_session.client("sts", config=BOTO_CLIENT_CONFIG)
    try:
        sts_response = sts_client.get_caller_identity()
    except:
        print("No or invalid AWS credentials configured")
        sys.exit(1)

    # Prepare target regions
    ec2_client = boto_session.client("ec2", config=BOTO_CLIENT_CONFIG)
    try:
        ec2_response = ec2_client.describe_regions(AllRegions=False)
        enabled_regions = [region["RegionName"] for region in ec2_response["Regions"]]
    except Exception as ex:
        print("Unable to list regions enabled in the account: {}".format(str(ex)))
        sys.exit(1)
    if args.regions == "ALL":
        args.regions = sorted(enabled_regions)
    else:
        for region in args.regions:
            if region not in enabled_regions:
                print("Invalid or disabled region for account: {}".format(region))
                sys.exit(1)

    # Prepare results directory
    results_directory = os.path.join(os.path.relpath(os.path.dirname(__file__) or "."), "results")
    try:
        os.mkdir(results_directory)
    except FileExistsError:
        pass

    # Prepare result collection structure
    run_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(TIMESTAMP_FORMAT)
    result_collection = {
        "_metadata": {
            "account_id": sts_response["Account"],
            "account_principal": sts_response["Arn"],
            "errors": {region: [] for region in args.regions},
            "invocation": " ".join(sys.argv),
            "run_timestamp": run_timestamp,
        },
        "regions": {region: {} for region in args.regions},
    }

    # Collect resources using one thread for each target region
    print("Analyzing account ID {}".format(sts_response["Account"]))
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for region in args.regions:
            executor.submit(analyze_region, region)

    # Write result file
    result_file = os.path.join(
        results_directory, "resources_{}_{}.json".format(sts_response["Account"], run_timestamp)
    )
    with open(result_file, "w") as out_file:
        json.dump(result_collection, out_file, indent=2, sort_keys=True)

    print("Output file written to {}".format(result_file))
