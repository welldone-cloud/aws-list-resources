# aws-list-resources

Uses the AWS Cloud Control API to list resources that are present in a given AWS account and region(s). Discovered resources are written to a JSON result file. See example result file [here](doc/example_results.json).

Main differences in comparison to using AWS Resource Explorer are:
* The AWS Cloud Control API supports a higher number of resources (see [here](https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html) vs. [here](https://docs.aws.amazon.com/resource-explorer/latest/userguide/supported-resource-types.html)).
* Creating views and indexes in AWS Resource Explorer requires write access to the underlying account. This script only requires read access.
* The AWS Cloud Control API returns global AWS resources in each AWS region. This means that, for example, if you target three AWS regions with this script, global resources like IAM roles or CloudFront distributions are shown three times in the result file.


## Usage

Make sure you have AWS credentials configured for your target environment. This can be done by using [environment 
variables](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html), or by using [aws login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html), or by specifying a [named 
profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html) in the optional `--profile` 
argument.

Ensure you run at least Python 3.10 (or newer) and install dependencies:

```bash
pip install -r requirements.txt
```

Example invocations:

```bash
python aws_list_resources.py --regions us-east-1,eu-central-1

python aws_list_resources.py --regions ALL --include-resource-types AWS::EC2::*,AWS::DynamoDB::*
```


## Supported arguments

```
--exclude-resource-types 
    Do not list the specified comma-separated resource types (supports wildcards).
--include-resource-types 
    Only list the specified comma-separated resource types (supports wildcards).
--only-store-counts 
    Only store resource counts instead of extended resource information.
--profile PROFILE
    Named AWS profile to use when running the command.
--regions REGIONS
    Comma-separated list of target AWS regions or 'ALL'.
```


## Notes

* The script can only discover resources that are supported by the `List` operation of the AWS Cloud Control API ([see here](https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html)).

* The script filters out default resources that AWS provides in each account and that often cannot be modified or deleted. However, AWS may create new default resources any time that the script does not correctly filter yet. Please create an issue in case you notice missing filters.


## Minimum IAM permissions required

The script requires read access to all AWS services you want to list resources for. As an example, if you want to list resources of the type `AWS::EC2::*`, you can grant permissions using the AWS-managed policy `AmazonEC2ReadOnlyAccess`. If you want to list any kind of resource type, you can use the AWS-managed policy `ReadOnlyAccess`. In any case, the following permissions are always required:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeRegions",
                "cloudformation:ListResources",
                "cloudformation:ListTypes"
            ],
            "Resource": "*"
        }
    ]
}
```

