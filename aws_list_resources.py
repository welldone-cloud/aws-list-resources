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
import packaging.requirements
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


def apply_default_resources_filter(resource_type, resources):
    """
    Filters out default resources that are always present in an AWS account, independent of whether the respective
    AWS service is actually used or not. Returns the list of remaining resources after applying the filter.
    """
    match resource_type:
        case "AWS::AppConfig::DeploymentStrategy":
            return {k: v for k, v in resources.items() if not k.startswith("AppConfig.")}

        case "AWS::AppConfig::Extension":
            return {k: v for k, v in resources.items() if "::extension/AWS." not in v["Arn"]}

        case "AWS::AppRunner::AutoScalingConfiguration":
            return {k: v for k, v in resources.items() if ":autoscalingconfiguration/DefaultConfiguration/" not in k}

        case "AWS::AppRunner::ObservabilityConfiguration":
            return {k: v for k, v in resources.items() if ":observabilityconfiguration/DefaultConfiguration/" not in k}

        case "AWS::Athena::DataCatalog":
            return {k: v for k, v in resources.items() if k != "AwsDataCatalog"}

        case "AWS::Athena::WorkGroup":
            return {k: v for k, v in resources.items() if k != "primary"}

        case "AWS::Backup::BackupVault":
            return {k: v for k, v in resources.items() if k != "Default"}

        case "AWS::Cassandra::Keyspace":
            return {k: v for k, v in resources.items() if k != "system_multiregion_info"}

        case "AWS::CloudFormation::PublicTypeVersion":
            return {k: v for k, v in resources.items() if "::type/" not in k}

        case "AWS::CloudFront::CachePolicy":
            default_resources = (
                "08627262-05a9-4f76-9ded-b50ca2e3a84f",
                "17322e93-4707-445a-93bc-6c8c16621822",
                "1b1c9610-973a-4fb9-9932-a6c274840887",
                "1c6db51a-a33f-469a-8245-dae26771f530",
                "2e54312d-136d-493c-8eb9-b001f22f67d2",
                "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                "4c02794c-7c81-4ba1-8b5d-e05fb0f95ed8",
                "4cc15a8a-d715-48a4-82b8-cc0b614638fe",
                "4d1d2f1d-3a71-49ad-9e08-7ea5d843a556",
                "658327ea-f89d-4fab-a63d-7e88639e58f6",
                "766eb028-1aff-4eb2-a5a4-2674e1538f26",
                "7e5fad67-ee98-4ad0-b05a-394999eefc1a",
                "83da9c7e-98b4-4e11-a168-04f0df8e2c65",
                "a6bad946-36c3-4c33-aa98-362c74a7fb13",
                "b2884449-e4de-46a7-ac36-70bc7f1ddd6d",
            )
            return {k: v for k, v in resources.items() if k not in default_resources}

        case "AWS::CloudFront::OriginRequestPolicy":
            default_resources = (
                "216adef6-5c7f-47e4-b989-5492eafa07d3",
                "33f36d7e-f396-46d9-90e0-52428a34d9dc",
                "59781a5b-3903-41f3-afcb-af62929ccde1",
                "775133bc-15f2-49f9-abea-afb2e0bf67d2",
                "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf",
                "acba4595-bd28-49b8-b9fe-13317c0390fa",
                "b689b0a8-53d0-40ab-baf2-68738e2966ac",
            )
            return {k: v for k, v in resources.items() if k not in default_resources}

        case "AWS::CloudFront::ResponseHeadersPolicy":
            default_resources = (
                "5cc3b908-e619-4b99-88e5-2cf7f45965bd",
                "60669652-455b-4ae9-85a4-c4c02393f86c",
                "67f7725c-6f97-4210-82d7-5512b31e9d03",
                "e61eb60c-9c35-4d20-a928-2b84e02af89c",
                "eaab4381-ed33-4a86-88ca-d9558dc6cd63",
            )
            return {k: v for k, v in resources.items() if k not in default_resources}

        case "AWS::CloudTrail::Dashboard":
            return {k: v for k, v in resources.items() if v["Type"] != "MANAGED"}

        case "AWS::CodeDeploy::DeploymentConfig":
            return {k: v for k, v in resources.items() if not k.startswith("CodeDeployDefault.")}

        case "AWS::CodePipeline::CustomActionType":
            default_resources = (
                "Approval|Manual|1",
                "Build|CodeBuild|1",
                "Build|ECRBuildAndPublish|1",
                "Compute|Commands|1",
                "Deploy|AlexaSkillsKit|1",
                "Deploy|AppConfig|1",
                "Deploy|CloudFormationStackInstances|1",
                "Deploy|CloudFormationStackSet|1",
                "Deploy|CloudFormation|1",
                "Deploy|CodeDeployToECS|1",
                "Deploy|CodeDeploy|1",
                "Deploy|EC2|1",
                "Deploy|ECS|1",
                "Deploy|EKS|1",
                "Deploy|ElasticBeanstalk|1",
                "Deploy|OpsWorks|1",
                "Deploy|S3|1",
                "Deploy|ServiceCatalog|1",
                "Invoke|CodePipeline|1",
                "Invoke|InspectorScan|1",
                "Invoke|Lambda|1",
                "Invoke|Snyk|1",
                "Invoke|StepFunctions|1",
                "Source|CodeCommit|1",
                "Source|CodeStarSourceConnection|1",
                "Source|ECR|1",
                "Source|GitHub|1",
                "Source|S3|1",
                "Test|CodeBuild|1",
                "Test|DeviceFarm|1",
                "Test|GhostInspector|1",
                "Test|MFStormRunner|1",
                "Test|Runscope|1",
            )
            return {k: v for k, v in resources.items() if k not in default_resources}

        case "AWS::EC2::PrefixList":
            return {k: v for k, v in resources.items() if v["OwnerId"] != "AWS"}

        case "AWS::ECS::CapacityProvider":
            default_resources = ("FARGATE", "FARGATE_SPOT")
            return {k: v for k, v in resources.items() if k not in default_resources}

        case "AWS::ElastiCache::ParameterGroup":
            return {k: v for k, v in resources.items() if not k.startswith("default.")}

        case "AWS::ElastiCache::User":
            return {k: v for k, v in resources.items() if k != "default"}

        case "AWS::Events::EventBus":
            return {k: v for k, v in resources.items() if k != "default"}

        case "AWS::GameLift::Location":
            default_resources = (
                "af-south-1",
                "af-south-1-los-1",
                "ap-east-1",
                "ap-northeast-1",
                "ap-northeast-2",
                "ap-northeast-3",
                "ap-south-1",
                "ap-southeast-1",
                "ap-southeast-2",
                "ca-central-1",
                "eu-central-1",
                "eu-north-1",
                "eu-south-1",
                "eu-west-1",
                "eu-west-2",
                "eu-west-3",
                "me-south-1",
                "sa-east-1",
                "us-east-1",
                "us-east-1-atl-1",
                "us-east-1-chi-1",
                "us-east-1-dfw-1",
                "us-east-1-iah-1",
                "us-east-1-mci-1",
                "us-east-2",
                "us-west-1",
                "us-west-2",
                "us-west-2-den-1",
                "us-west-2-lax-1",
                "us-west-2-phx-1",
            )
            return {k: v for k, v in resources.items() if k not in default_resources}

        case "AWS::IAM::ManagedPolicy":
            return {k: v for k, v in resources.items() if not k.startswith("arn:aws:iam::aws:policy/")}

        case "AWS::IoT::DomainConfiguration":
            default_resources = ("iot:CredentialProvider", "iot:Data-ATS", "iot:Jobs")
            return {k: v for k, v in resources.items() if k not in default_resources}

        case "AWS::KMS::Alias":
            return {k: v for k, v in resources.items() if not k.startswith("alias/aws/")}

        case "AWS::MediaLive::CloudWatchAlarmTemplate":
            return {k: v for k, v in resources.items() if "::cloudwatch-alarm-template:aws-" not in v["Arn"]}

        case "AWS::MediaLive::CloudWatchAlarmTemplateGroup":
            return {k: v for k, v in resources.items() if "::cloudwatch-alarm-template-group:aws-" not in v["Arn"]}

        case "AWS::MemoryDB::ACL":
            return {k: v for k, v in resources.items() if k != "open-access"}

        case "AWS::MemoryDB::ParameterGroup":
            return {k: v for k, v in resources.items() if not k.startswith("default.")}

        case "AWS::MemoryDB::User":
            return {k: v for k, v in resources.items() if k != "default"}

        case "AWS::RAM::Permission":
            return {k: v for k, v in resources.items() if v["PermissionType"] != "AWS_MANAGED"}

        case "AWS::RDS::DBClusterParameterGroup":
            return {k: v for k, v in resources.items() if not k.startswith("default.")}

        case "AWS::RDS::DBParameterGroup":
            return {k: v for k, v in resources.items() if not k.startswith("default.")}

        case "AWS::RDS::OptionGroup":
            return {k: v for k, v in resources.items() if not k.startswith("default:")}

        case "AWS::Route53Resolver::FirewallDomainList":
            return {k: v for k, v in resources.items() if not v["CreatorRequestId"].startswith("AWSManaged")}

        case "AWS::Route53Resolver::ResolverRule":
            return {k: v for k, v in resources.items() if not k.startswith("rslvr-autodefined-")}

        case "AWS::Route53Resolver::ResolverRuleAssociation":
            return {k: v for k, v in resources.items() if not k.startswith("rslvr-autodefined-")}

        case "AWS::S3::StorageLens":
            return {k: v for k, v in resources.items() if k != "default-account-dashboard"}

        case "AWS::SSM::Document":
            default_prefixes = (
                "AWS",
                "AlertLogic",
                "Amazon",
                "Aws",
                "CrowdStrike",
                "Dynatrace",
                "FalconSensor",
                "New-Relic",
                "SSM",
                "TrendMicro",
            )
            return {
                k: v for k, v in resources.items() if not any([k.startswith(prefix) for prefix in default_prefixes])
            }

        case "AWS::SSM::PatchBaseline":
            return {k: v for k, v in resources.items() if not v["Name"].startswith("AWS-")}

        case "AWS::Scheduler::ScheduleGroup":
            return {k: v for k, v in resources.items() if k != "default"}

        case "AWS::XRay::Group":
            return {k: v for k, v in resources.items() if ":group/Default" not in k}

        case "AWS::XRay::SamplingRule":
            return {k: v for k, v in resources.items() if ":sampling-rule/Default" not in k}

        case _:
            return resources


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
    collected_resources = {}
    list_resources_paginator = cloudcontrol_client.get_paginator("list_resources")
    try:
        for list_resources_page in list_resources_paginator.paginate(TypeName=resource_type):
            for resource in list_resources_page["ResourceDescriptions"]:
                collected_resources[resource["Identifier"]] = json.loads(resource["Properties"])

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
    """
    Logs the given error message to both the result file and to stdout.
    """
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
            resources = apply_default_resources_filter(resource_type, resources)
            if resources:
                if args.only_show_counts:
                    result_collection["regions"][region][resource_type] = len(resources)
                else:
                    result_collection["regions"][region][resource_type] = resources

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
        for requirements_line in requirements_file.read().splitlines():
            requirement = packaging.requirements.Requirement(requirements_line)
            expected_version_specifier = requirement.specifier
            installed_version = packaging.version.parse(importlib.metadata.version(requirement.name))
            if installed_version not in expected_version_specifier:
                print("Unfulfilled requirement: {}".format(requirements_line))
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
        help="only show resource counts instead of extended resource information",
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

    print("Result file written to {}".format(result_file))
