#!/usr/bin/env python3

import argparse
import bisect
import boto3
import botocore.config
import concurrent.futures
import datetime
import json
import os
import sys
import zlib
from threading import Lock

BOTO_CLIENT_CONFIG = botocore.config.Config(retries={"total_max_attempts": 5, "mode": "standard"})


class DeniedListOperationException(Exception):
    """
    Raised when the "List" operation of the Cloud Control API failed due to permission errors.
    """


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
    print("{}, {}".format(cloudcontrol_client._client_config.region_name, resource_type))
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


def analyze_resource(boto_session, region, resource_type, result_collection, only_show_counts):
    """
    Lists resources of a specific resource type in the given region and adds them to the result collection.
    """
    cloudcontrol_client = boto_session.client("cloudcontrol", config=BOTO_CLIENT_CONFIG)
    try:
        resources = get_resources(cloudcontrol_client, resource_type)
        if resources:
            if only_show_counts:
                with thread_lock:  # Ensure thread-safe access to result_collection
                    result_collection["regions"][region][resource_type] = len(resources)
            else:
                with thread_lock:  # Ensure thread-safe access to result_collection
                    result_collection["regions"][region][resource_type] = sorted(resources)

    except DeniedListOperationException:
        with thread_lock:  # Ensure thread-safe access to result_collection
            bisect.insort(result_collection["_metadata"]["denied_list_operations"][region], resource_type)



if __name__ == "__main__":
    # Check runtime environment
    if sys.version_info[0] < 3:
        print("Python version 3 required")
        sys.exit(1)

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only-show-counts",
        required=False,
        default=False,
        action="store_true",
        help="only show resource counts instead of listing their full identifiers",
    )
    parser.add_argument("--profile", required=False, nargs=1, help="optional named AWS profile to use")
    parser.add_argument("--regions", required=False, nargs=1, help="comma-separated list of target AWS regions")

    args = parser.parse_args()
    only_show_counts = args.only_show_counts
    profile = args.profile[0] if args.profile else None
    boto_session = boto3.session.Session(profile_name=profile)


    if args.regions:
        target_regions = [region for region in args.regions[0].split(",") if region]
    else:
        ec2_client = boto_session.client("ec2", region_name = "eu-west-1")
        target_regions = [region.get("RegionName") for region in ec2_client.describe_regions(AllRegions=False).get("Regions", [])]
        print(f"No regions specified so resources will be collected resource across all enabled regions ({len(target_regions)})")

    # Test for valid credentials
    sts_client = boto_session.client("sts", config=BOTO_CLIENT_CONFIG)
    try:
        sts_response = sts_client.get_caller_identity()
    except:
        print("No or invalid AWS credentials configured")
        sys.exit(1)

    # Prepare results directory
    results_directory = os.path.join(os.path.relpath(os.path.dirname(__file__)), "results")
    try:
        os.mkdir(results_directory)
    except FileExistsError:
        pass

    # Prepare result collection structure
    run_timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    result_collection = {
        "_metadata": {
            "account_id": sts_response["Account"],
            "account_principal": sts_response["Arn"],
            "denied_list_operations": {region: [] for region in target_regions},
            "run_timestamp": run_timestamp,
        },
        "regions": {region: {} for region in target_regions},
    }

    # Initialize a lock for thread-safe operations
    thread_lock = Lock()

    # Collect resources using one thread for each target region
    print("Analyzing account ID {}".format(sts_response["Account"]))
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for region in target_regions:
            boto_session = boto3.session.Session(profile_name=profile, region_name=region)
            # Create a client for the region to list resource types
            cloudformation_client = boto_session.client("cloudformation", config=BOTO_CLIENT_CONFIG)
            try:
                resource_types = get_supported_resource_types(cloudformation_client)
            except Exception as ex:
                msg = "Error: unable to list resource types for region {}: {}".format(region, str(ex))
                result_collection["_metadata"]["denied_list_operations"][region].append(msg)
                print(msg)
                continue # Skip to the next region if unable to list resource types

            for resource_type in resource_types:
                # Submit a task to the executor for each resource type
                futures.append(executor.submit(analyze_resource, boto_session, region, resource_type, result_collection, only_show_counts))
    
    # Wait for all tasks to complete
    concurrent.futures.wait(futures)

    # Write result file
    result_file = os.path.join(
        results_directory, "resources_{}_{}.json".format(sts_response["Account"], run_timestamp)
    )
    with open(result_file, "w") as out_file:
        json.dump(result_collection, out_file, indent=2, sort_keys=True)

    print("Output file written to {}".format(result_file))
