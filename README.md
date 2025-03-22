# aws-list-resources

Uses the AWS Cloud Control API to list resources that are present in a given AWS account and region(s). Discovered resources are written to a JSON result file. See example result file [here](doc/example_results.json).


## Usage

Make sure you have AWS credentials configured for your target account. This can either be done using [environment variables](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html) or by specifying a [named profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html) in the optional `--profile` argument.

Install dependencies:

```bash
pip install -r requirements.txt
```

Example invocations:

```bash
python aws_list_resources.py --regions us-east-1,eu-central-1

python aws_list_resources.py --regions ALL

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
--show-stats
    Show stats about collected resources at the end of the run. Can contain duplicates due to AWS returning the same resources for multiple regions.
--profile PROFILE
    Named AWS profile to use when running the command.
--regions REGIONS
    Comma-separated list of target AWS regions or 'ALL'.
```


## Notes

* The script can only discover resources that are supported by the AWS Cloud Control API and offer support for the `List` operation: [https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html](https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html)

* The script filters out default resources that AWS provides in each account and that often cannot be modified or deleted. However, AWS may create new default resources any time that the script does not correctly filter yet. Please create an issue in case you notice missing filters.


## Minimum IAM permissions required

The script requires read access to all AWS services you want to list resources for. As an example, if you want to list resources of the type `AWS::EC2::*`, you can grant permissions using the AWS-managed policy `AmazonEC2ReadOnlyAccess`. If you want to list any kind of resource type, you can use the AWS-managed policy `ReadOnlyAccess`. Additionally, the following permissions are required:

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

