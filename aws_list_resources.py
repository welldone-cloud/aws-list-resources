#!/usr/bin/env python3

import argparse
import boto3
import concurrent.futures
import datetime
import json
import sys


def get_available_resource_types(region):
    cloudformation_client = boto3.client(
        "cloudformation",
        region_name=region
    )
    resource_types = set()
    provisioning_types = ("FULLY_MUTABLE", "IMMUTABLE")
    for provisioning_type in provisioning_types:
        call_params = {
            "Type": "RESOURCE",
            "Visibility": "PUBLIC",
            "ProvisioningType": provisioning_type,
            "DeprecatedStatus": "LIVE",
            "Filters": {
                "Category": "AWS_TYPES"
            }
        }
        while True:
            cloudformation_response = cloudformation_client.list_types(
                **call_params
            )
            for type in cloudformation_response["TypeSummaries"]:
                resource_types.add(type["TypeName"])
            try:
                call_params["NextToken"] = cloudformation_response["NextToken"]
            except KeyError:
                break

    return sorted(resource_types)


def get_resources(region, resource_type):
    cloudcontrol_client = boto3.client(
        "cloudcontrol",
        region_name=region
    )
    print("{}, {}".format(region, resource_type))
    collected_resources = []
    call_params = {"TypeName": resource_type}
    try:
        while True:
            cloudcontrol_response = cloudcontrol_client.list_resources(
                **call_params
            )
            for resource in cloudcontrol_response["ResourceDescriptions"]:
                collected_resources.append(resource["Identifier"])
            try:
                call_params["NextToken"] = cloudcontrol_response["NextToken"]
            except KeyError:
                break
    except:
        # There is unfortunately a long and non-uniform list of exceptions that can occur with the Cloud Control API,
        # presumably because it just passes through the exceptions of the underlying services. Examples are when the
        # "List" operation requires additional parameters or when the caller lacks permissions for an API call:
        # UnsupportedActionException, InvalidRequestException, GeneralServiceException, ResourceNotFoundException,
        # HandlerInternalFailureException, AccessDeniedException, AuthorizationError, etc. As the end result is the
        # same (resources cannot be listed), they are all caught by this broad except clause.
        pass

    return (resource_type, sorted(collected_resources))


if __name__ == "__main__":
    # Parse target region(s)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--regions",
        required=True,
        help="comma-separated list of targeted AWS regions"
    )
    args = parser.parse_args()
    target_regions = [region for region in args.regions.split(",") if region]

    # Test for valid credentials and get the target account ID
    sts_client = boto3.client("sts")
    try:
        sts_response = sts_client.get_caller_identity()
        account_id = sts_response["Account"]
        print("Analyzing account ID {}".format(account_id))
    except:
        print("No or invalid AWS credentials configured")
        sys.exit(1)

    # Collect resources for each target region
    resources_collected = {}
    for region in target_regions:
        resource_types = get_available_resource_types(region)
        resources_collected[region] = {}

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for resource_type in resource_types:
                future = executor.submit(get_resources, region, resource_type)
                futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                resource_type, resources = future.result()
                if resources:
                    resources_collected[region][resource_type] = resources

    # Write result file
    output_file_name = "resources_{}_{}.json".format(
        account_id,
        datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    )
    with open(output_file_name, "w") as out_file:
        json.dump(resources_collected, out_file, indent=2, sort_keys=True)

    print("Output file written to {}".format(output_file_name))
