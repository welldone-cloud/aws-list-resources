# aws-list-resources

Uses the AWS Cloud Control API to list resources that are present in a given AWS account and region(s). Discovered resources are written to a JSON result file. See example result file [here](doc/example_results.json).

Main differences in comparison to using AWS Resource Explorer are:
* The AWS Cloud Control API supports a higher number of resources (see [here](https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html) vs. [here](https://docs.aws.amazon.com/resource-explorer/latest/userguide/supported-resource-types.html)).
* Creating views and indexes in AWS Resource Explorer requires write access to the underlying account. This script only requires read access.
* The AWS Cloud Control API returns global AWS resources in each AWS region. This means that, for example, it is sufficient to scan your primary AWS region and global resources like IAM roles or CloudFront distributions will also be shown in the result file.


## Usage

Make sure you have AWS credentials configured for your target environment. This can be done by using [environment 
variables](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html), or by using [aws login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html), or by specifying a [named 
profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html) in the optional `--profile` 
argument.

Ensure you run at least Python 3.11 (or newer) and install dependencies:

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

* The script filters out default resources that AWS creates in each account and that often cannot be modified or deleted. However, AWS may create new default resources any time that the script does not correctly filter yet. Please create an issue in case you notice missing filters.


## IAM permissions required

The script requires read access to the CloudFormation service and to all AWS services you want to list resources for. It does not require write access and does not make any mutating API calls. 

In practice, there is a balance between granting only the permissions required and being able to list a high number of different resource types within an account:

| AWS-managed policy | Resource type coverage | Comment | 
| -------- | ------- | ------- |
| `ViewOnlyAccess` | Medium | This policy grants your principal only permissions to read metadata within your AWS account. However, it is not well-maintained by AWS: Permissions to list certain resource types may not be granted at all, or the policy is only updated with a significant delay after a new service or feature was released. |
| `ReadOnlyAccess` | High | This policy grants your principal permissions to read both metadata and content within your AWS account. It is better maintained than `ViewOnlyAccess` and can thus list a higher number resource types. |
| `AdministratorAccess` | Highest | This policy grants your principal full read and write access within your AWS account. On the other hand, it is also capable of listing the most resource types: AWS service teams do not need to actively adapt this policy when releasing a new service or feature, because all API calls are allowed by default. |

In case the script does not have permissions to list a certain resource type, an error message will be shown on the console output and in the result file (`"Access denied to list resource type [...]"`).

