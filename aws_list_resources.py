#!/usr/bin/env python3

import argparse
import boto3
import botocore.config
import concurrent.futures
import datetime
import json
import random
import sys


BOTO_CONFIG = botocore.config.Config(retries={"total_max_attempts": 5, "mode": "standard"})

MAX_THREADS_FOR_REGIONS = 8


def get_supported_resource_types(region):
    """
    Returns a list of resource types that are supported in a region by querying the CloudFormation registry.
    Examples: AWS::EC2::RouteTable, AWS::IAM::Role, AWS::KMS::Key, etc.
    """
    resource_types = set()
    cloudformation_client = boto_session.client("cloudformation", region_name=region, config=BOTO_CONFIG)

    provisioning_types = ("FULLY_MUTABLE", "IMMUTABLE")
    for provisioning_type in provisioning_types:
        call_params = {
            "Type": "RESOURCE",
            "Visibility": "PUBLIC",
            "ProvisioningType": provisioning_type,
            "DeprecatedStatus": "LIVE",
            "Filters": {"Category": "AWS_TYPES"},
        }
        while True:
            cloudformation_response = cloudformation_client.list_types(**call_params)
            for type in cloudformation_response["TypeSummaries"]:
                resource_types.add(type["TypeName"])
            try:
                call_params["NextToken"] = cloudformation_response["NextToken"]
            except KeyError:
                break

    return list(resource_types)


def get_resources(region, resource_type):
    """
    Returns a list of resources of the given resource type discovered in the given region. Uses the "List" operation
    of the Cloud Control API. If the API call failed, an empty list is returned. If the API call likely failed because
    of permission issues, an additional flag is set in the return value.
    """
    print("{}, {}".format(region, resource_type))
    collected_resources = []
    list_operation_was_denied = False
    cloudcontrol_client = boto_session.client("cloudcontrol", region_name=region, config=BOTO_CONFIG)

    call_params = {"TypeName": resource_type}
    try:
        while True:
            cloudcontrol_response = cloudcontrol_client.list_resources(**call_params)
            for resource in cloudcontrol_response["ResourceDescriptions"]:
                collected_resources.append(resource["Identifier"])
            try:
                call_params["NextToken"] = cloudcontrol_response["NextToken"]
            except KeyError:
                break

    except Exception as ex:
        # There is unfortunately a long and non-uniform list of exceptions that can occur with the Cloud Control API,
        # presumably because it just passes through the exceptions of the underlying services. Examples for when the
        # "List" operation requires additional parameters or when the caller lacks permissions for an API call:
        # UnsupportedActionException, InvalidRequestException, GeneralServiceException, ResourceNotFoundException,
        # HandlerInternalFailureException, AccessDeniedException, AuthorizationError, etc. They are thus handled by
        # this broad except clause. The end result is the same: resources for this resource type cannot be listed.

        # Flag when the "List" operation was likely denied due to a lack of permissions
        exception_msg = str(ex).lower()
        for keyword in ("denied", "authorization", "authorized"):
            if keyword in exception_msg:
                list_operation_was_denied = True
                break

    return (resource_type, list_operation_was_denied, sorted(collected_resources))


def analyze_region(region):
    """
    Lists all resources of supported resources types in the given region and adds them to the result collection.
    """
    # Shuffle the list of supported resource types to avoid API throttling (e.g., avoid listing all resources of
    # the EC2 API namespace within only a few seconds, but spread requests out)
    resource_types = get_supported_resource_types(region)
    random.shuffle(resource_types)

    # Use threads to list the resources of each resource type. Using a higher number of threads here unfortunately
    # leads to API throttling instead of being faster. Also keep in mind that each region is already analyzed by a
    # separate thread, so this is only an in-region acceleration.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        for resource_type in resource_types:
            future = executor.submit(get_resources, region, resource_type)
            futures.append(future)

        for future in concurrent.futures.as_completed(futures):
            resource_type, list_operation_was_denied, resources = future.result()
            if list_operation_was_denied:
                result_collection["_metadata"]["denied_list_operations"][region].append(resource_type)
            if resources:
                if only_show_counts:
                    result_collection["regions"][region][resource_type] = len(resources)
                else:
                    result_collection["regions"][region][resource_type] = resources

    result_collection["_metadata"]["denied_list_operations"][region].sort()


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
    parser.add_argument("--regions", required=True, nargs=1, help="comma-separated list of targeted AWS regions")

    args = parser.parse_args()
    only_show_counts = args.only_show_counts
    profile = args.profile[0] if args.profile else None
    target_regions = [region for region in args.regions[0].split(",") if region]
    boto_session = boto3.session.Session(profile_name=profile)

    # Test for valid credentials
    sts_client = boto_session.client("sts", config=BOTO_CONFIG)
    try:
        sts_response = sts_client.get_caller_identity()
    except:
        print("No or invalid AWS credentials configured")
        sys.exit(1)

    # Prepare result collection structure
    run_timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    result_collection = {
        "_metadata": {
            "account_id": sts_response["Account"],
            "account_principal": sts_response["Arn"],
            "denied_list_operations": {},
            "run_timestamp": run_timestamp,
        },
        "regions": {},
    }
    for region in target_regions:
        result_collection["regions"][region] = {}
        result_collection["_metadata"]["denied_list_operations"][region] = []

    # Collect resources using a separate thread for each target region
    print("Analyzing account ID {}".format(sts_response["Account"]))
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS_FOR_REGIONS) as executor:
        for region in target_regions:
            executor.submit(analyze_region, region)

    # Write result file
    output_file_name = "resources_{}_{}.json".format(sts_response["Account"], run_timestamp)
    with open(output_file_name, "w") as out_file:
        json.dump(result_collection, out_file, indent=2, sort_keys=True)

    print("Output file written to {}".format(output_file_name))
