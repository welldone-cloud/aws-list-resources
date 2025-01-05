# aws-list-resources

Uses the AWS Cloud Control API to list resources that are present in a given AWS account and region(s). Discovered resources are written to a JSON output file. 


## Usage

Make sure you have AWS credentials configured for your target account. This can either be done using [environment variables](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html) or by specifying a [named profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html) in the optional `--profile` argument. Read-only IAM permissions are sufficient. 

Install dependencies:

```bash
pip install -r requirements.txt
```

Example invocations:

```bash
python aws_list_resources.py --regions us-east-1,eu-central-1

python aws_list_resources.py --regions ALL

python aws_list_resources.py --regions ALL --include-resource-types AWS::EC2::*,AWS::DynamoDB::* --exclude-resource-types AWS::EC2::DHCPOptions,AWS::EC2::VPCGatewayAttachment
```


## Supported arguments

```
--exclude-resource-types  do not list the specified comma-separated resource types (supports wildcards)
--include-resource-types  only list the specified comma-separated resource types (supports wildcards)
--only-show-counts        only show resource counts instead of listing their full identifiers
--profile PROFILE         named AWS profile to use when running the command
--regions REGIONS         comma-separated list of target AWS regions or 'ALL'
```


## Notes

* The script will only be able to discover resources that are currently supported by the AWS Cloud Control API and offer support for the `List` operation:

  https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html
  
  It is further restricted to those resources where the `List` operation does not expect any additional parameters.

* If the IAM user or role you use to run the script does not have permissions to interact with certain AWS services or regions, those resources will be missed. Note that permissions can be restricted on different levels, such as SCPs, identity-based polices, etc. The JSON output file will contain information on resource types where listing was not successful.

* The JSON output file will also contain default resources that were created by AWS, independent of whether you actually used the service or not.


## Example output file

Truncated example JSON output file:
```json
{
  "_metadata": {
    "account_id": "123456789012",
    "account_principal": "arn:aws:iam::123456789012:user/myuser",
    "invocation": "aws_list_resources.py --regions us-east-1,eu-central-1",
    "run_timestamp": "20250105134120"
    // ...
  },
  "regions": {
    "us-east-1": {
      "AWS::Athena::DataCatalog": [
        "AwsDataCatalog"
      ],
      "AWS::CloudFront::CachePolicy": [
        "08627262-05a9-4f76-9ded-b50ca2e3a84f",
        "2e54312d-136d-493c-8eb9-b001f22f67d2",
        "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
        "658327ea-f89d-4fab-a63d-7e88639e58f6",
        "b2884449-e4de-46a7-ac36-70bc7f1ddd6d"
      ],
      "AWS::EC2::DHCPOptions": [
        "dopt-0aff9c4854b33dc5c"
      ],
      "AWS::EC2::InternetGateway": [
        "igw-0090532d0f608e279"
      ],
      "AWS::EC2::NetworkAcl": [
        "acl-0451d5fc3be271330"
      ],
      "AWS::EC2::RouteTable": [
        "rtb-077ff6c625794e4fe"
      ],
      "AWS::IAM::Role": [
        "AWSServiceRoleForCloudTrail",
        "AWSServiceRoleForGlobalAccelerator",
        "AWSServiceRoleForOrganizations",
        "AWSServiceRoleForSupport",
        "AWSServiceRoleForTrustedAdvisor",
        "OrganizationAccountAccessRole"
      ],
      // ...
    }
  }
}
```
