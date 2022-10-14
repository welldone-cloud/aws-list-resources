# AWS list resources

Uses the AWS Cloud Control API to list resources that are present in a given AWS account and region(s). Discovered
resources are written to a JSON output file.


## Usage

Make sure you have AWS credentials configured for your target account (e.g., using environment variables) and
run:
```bash
pip install -r requirements.txt

python aws_list_resources.py --regions eu-central-1
python aws_list_resources.py --regions eu-west-1,us-east-1
```


## Notes

* The script will only be able to discover resources that are currently supported by the AWS Cloud Control API and
  offer support for the "List" operation:
  https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html
  
  It is further restricted to those resources where the "List" operation does not expect any additional parameters.

* If the IAM user or role you use to run the script does not have permissions to interact with certain AWS services or
  regions, those resources will be missed without further warning. Please note that permission restrictions may be
  configured on different levels, such as SCPs, identity-based polices, etc.

* The JSON output file will also contain default resources that were created by AWS, independent of whether you 
  actually used the respective service or not.


## Example output file (truncated)

```json
{
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
    [...]
  }
}
```
