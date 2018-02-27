#
# Copyright 2017-2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.
#

#
# This Rule is part of the Security Epics RuleSet. This RuleSet provides guidance on the Security Epics of the AWS Cloud Adoption Framework (CAF)
#
# Identity and Access Management
# 1.1 | root_no_access
# 1.2 | root_mfa_enabled
# 1.3 | root_no_access_key
# 1.4 | iam_policy_no_full_star
# 1.5 | iam_no_user_except_system_and_breakglass

import json
import boto3
import sys
import csv
import time
from datetime import datetime

STS_SESSION = ''
RESULT_TOKEN = 'No token found.'

def get_sts_session(event, rolename, region_name=False):
    sts = boto3.client("sts")
    role_arn = str("arn:aws:iam::" + event['configRuleArn'].split(":")[4] + ":role/" + rolename)
    if not region_name:
        region_name = event['configRuleArn'].split(":")[3]
    response = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName='ComplianceAudit',
        DurationSeconds=900)
    sts_session = boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken'],
        region_name=region_name,
        botocore_session=None,
        profile_name=None)
    return sts_session

def IAM_1_1_root_no_access():
    iam = STS_SESSION.client("iam")
    credreport = get_cred_report()
    if "Fail" in credreport:  # Report failure in control
        sys.exit(credreport)

    # Check if root is used in the last 24h
    now = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time()))
    frm = "%Y-%m-%dT%H:%M:%S+00:00"
    status = 'COMPLIANT'

    try:
        pwdDelta = (datetime.strptime(now, frm) - datetime.strptime(credreport[0]['password_last_used'], frm))
        if (pwdDelta.days == 0) & (pwdDelta.seconds > 0):  # Used within last 24h
            status = 'NON_COMPLIANT'
    except:
        if credreport[0]['password_last_used'] == "N/A" or "no_information":
            pass
        else:
            print("Something went wrong")

    try:
        key1Delta = (datetime.strptime(now, frm) - datetime.strptime(credreport[0]['access_key_1_last_used_date'], frm))
        if (key1Delta.days == 0) & (key1Delta.seconds > 0):  # Used within last 24h
            status = 'NON_COMPLIANT'
    except:
        if credreport[0]['access_key_1_last_used_date'] == "N/A" or "no_information":
            pass
        else:
            print("Something went wrong")
    try:
        key2Delta = datetime.strptime(now, frm) - datetime.strptime(credreport[0]['access_key_2_last_used_date'], frm)
        if (key2Delta.days == 0) & (key2Delta.seconds > 0):  # Used within last 24h
            status = 'NON_COMPLIANT'
    except:
        if credreport[0]['access_key_2_last_used_date'] == "N/A" or "no_information":
            pass
        else:
            print("Something went wrong")


    config = STS_SESSION.client("config")
    config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType": "AWS::::Account",
                "ComplianceResourceId": "Root No Access",
                "ComplianceType": status,
                "OrderingTimestamp": str(datetime.now())
            },
        ],
        ResultToken=RESULT_TOKEN
    )

def IAM_1_2_user_mfa_enabled(event):
    iam = STS_SESSION.client("iam")
    APPLICABLE_RESOURCES = ['AWS::IAM::User']
    configuration_item = json.loads(event['invokingEvent']['configurationItem'])
    if configuration_item['resourceType'] not in APPLICABLE_RESOURCES:
        status = 'NOT_APPLICABLE'
    user_name = configuration_item['resourceName']
    mfa_devices = iam.list_mfa_devices(UserName=user_name)

    # Only check MFA on User with passwords
    try:
        profile = iam.get_login_profile(UserName=user_name)
    except:
        status = 'NOT_APPLICABLE'

    if len(mfa_devices['MFADevices']) < 1:
        status = 'NON_COMPLIANT'
    else:
        status = 'COMPLIANT'

    config = STS_SESSION.client("config")
    config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType": configuration_item['resourceType'],
                "ComplianceResourceId": "User MFA Enabled",
                "ComplianceType": status,
                "OrderingTimestamp": str(datetime.now())
            },
        ],
        ResultToken=RESULT_TOKEN
    )

def IAM_1_12_root_no_access_key():
    iam = STS_SESSION.client("iam")
    credreport = get_cred_report()
    if "Fail" in credreport:  # Report failure in control
        sys.exit(credreport)

    if (credreport[0]['access_key_1_active'] == "true") or (credreport[0]['access_key_2_active'] == "true"):
        status = 'NON_COMPLIANT'
    else:
        status = 'COMPLIANT'

    config = STS_SESSION.client("config")
    config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType": "AWS::::Account",
                "ComplianceResourceId": "Root No Access Key",
                "ComplianceType": status,
                "OrderingTimestamp": str(datetime.now())
            },
        ],
        ResultToken=RESULT_TOKEN
    )

def IAM_1_13_root_mfa_enabled():
    iam = STS_SESSION.client("iam")
    response = iam.get_account_summary()
    if response['SummaryMap']['AccountMFAEnabled'] != 1:
        status = 'NON_COMPLIANT'
    else:
        status = 'COMPLIANT'

    config = STS_SESSION.client("config")
    config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType": "AWS::::Account",
                "ComplianceResourceId": "Root MFA enabled",
                "ComplianceType": status,
                "OrderingTimestamp": str(datetime.now())
            },
        ],
        ResultToken=RESULT_TOKEN
    )

def IAM_1_14_root_hardware_mfa():
    iam = STS_SESSION.client("iam")
    response = iam.list_virtual_mfa_devices()['VirtualMFADevices']
    for mfa_device in response:
        if 'SerialNumber' in mfa_device:
            status = 'NON_COMPLIANT'
            break
        else:
            status = 'COMPLIANT'

    config = STS_SESSION.client("config")
    config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType": "AWS::::Account",
                "ComplianceResourceId": "Root Hardware MFA",
                "ComplianceType": status,
                "Annotation": "The root account should use a hardware-based MFA device.",
                "OrderingTimestamp": str(datetime.now())
            },
        ],
        ResultToken=RESULT_TOKEN
    )

def IAM_1_16_iam_policies_only_group_roles(event):
    iam = STS_SESSION.client("iam")
    APPLICABLE_RESOURCES = ['AWS::IAM::User']
    configuration_item = json.loads(event['invokingEvent']['configurationItem'])
    if configuration_item['resourceType'] not in APPLICABLE_RESOURCES:
        status = 'NOT_APPLICABLE'
    user_name = configuration_item['resourceName']

    if iam.list_user_policies(UserName=user_name)['PolicyNames'] \
        or iam.list_attached_user_policies(UserName=user_name)['AttachedPolicies']:
        status = 'NON_COMPLIANT'
    else:
        status = 'COMPLIANT'

    config = STS_SESSION.client("config")
    config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType": "AWS::IAM::User",
                "ComplianceResourceId": "IAM Policies attached to Groups and Roles",
                "ComplianceType": status,
                "OrderingTimestamp": str(datetime.now())
            },
        ],
        ResultToken=RESULT_TOKEN
    )

def IAM_1_21_instance_role_use(event):
    ec2 = STS_SESSION.client("ec2")
    configuration_item = json.loads(event['invokingEvent']['configurationItem'])
    instance_id = configuration_item['resourceId']
    reservations = ec2.describe_instances(InstanceIds=[instance_id])['Reservations']

    if reservations and 'IamInstanceProfile' in reservations[0]['Instances'][0]:
        status = 'COMPLIANT'
    else:
        status = 'NON_COMPLIANT'

    config = STS_SESSION.client("config")
    config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType": "AWS::EC2::Instance",
                "ComplianceResourceId": "Instance Profile Use",
                "ComplianceType": status,
                "OrderingTimestamp": str(datetime.now())
            },
        ],
        ResultToken=RESULT_TOKEN
    )

def IAM_1_24_iam_policy_no_full_star():
    iam = STS_SESSION.client("iam")
    response = iam.list_policies(Scope='Local')

    for configuration_item in response["Policies"]:
        policy_info = iam.get_policy(PolicyArn=configuration_item["Arn"])
        print policy_info
        if policy_info["Policy"]["IsAttachable"] is False:
            status = "NOT_APPLICABLE"
        else:
            policy_version = iam.get_policy_version(PolicyArn=configuration_item["Arn"], VersionId=policy_info['Policy']['DefaultVersionId'])
            for statement in policy_version['PolicyVersion']['Document']['Statement']:

                star_statement = False
                if type(statement['Action']) is list:
                    for action in statement['Action']:
                        if action == "*":
                            star_statement = True
                else: # just one Action
                    if statement['Action'] == "*":
                        star_statement = True

                star_resource = False
                if type(statement['Resource']) is list:
                    for action in statement['Resource']:
                        if action == "*":
                            star_resource = True
                else: # just one Resource
                    if statement['Resource'] == "*":
                        star_resource = True

                if star_statement and star_resource:
                    status = 'NON_COMPLIANT'
                else:
                    status = 'COMPLIANT'

        ResourceId = configuration_item["PolicyId"]
        ResourceType = "AWS::IAM::Policy"
        config = STS_SESSION.client("config")
        config.put_evaluations(
            Evaluations=[
                {
                    "ComplianceResourceType": ResourceType,
                    "ComplianceResourceId": ResourceId,
                    "ComplianceType": status,
                    "Annotation": "No full * (aka full permission) in an IAM Policy should be attached to IAM Users/Groups/Roles.",
                    "OrderingTimestamp": str(datetime.now())
                },
            ],
            ResultToken=RESULT_TOKEN
        )

    # Verify the AWS managed policy named AdminstratorAccess
    admin_response = iam.get_policy(PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess")
    ResourceType = "AWS::IAM::ManagedPolicy"
    ResourceId = "AdministratorAccess"
    if int(admin_response["Policy"]["AttachmentCount"]) > 0:
        status = "NON_COMPLIANT"
    else:
        status = "COMPLIANT"

    config = STS_SESSION.client("config")
    config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType": ResourceType,
                "ComplianceResourceId": ResourceId,
                "ComplianceType": status,
                "Annotation": "No full * (aka full permission) in an IAM Policy should be attached to IAM Users/Groups/Roles.",
                "OrderingTimestamp": str(datetime.now())
            },
        ],
        ResultToken=RESULT_TOKEN
    )

def get_cred_report():
    status = ''
    x = 0
    iam = STS_SESSION.client("iam")
    while iam.generate_credential_report()['State'] != "COMPLETE":
        time.sleep(2)
        x += 1
        # If no credentail report is delivered within this time fail the check.
        if x > 10:
            status = "Fail: rootUse - no CredentialReport available."
            break
    if "Fail" in status:
        return status
    credentialReport = str(iam.get_credential_report()['Content'],'utf-8')
    report = []
    reader = csv.DictReader(credentialReport.splitlines())
    for row in reader:
        report.append(row)

    # Verify if root key's never been used, if so add N/A
    try:
        if report[0]['access_key_1_last_used_date']:
            pass
    except:
        report[0]['access_key_1_last_used_date'] = "N/A"
    try:
        if report[0]['access_key_2_last_used_date']:
            pass
    except:
        report[0]['access_key_2_last_used_date'] = "N/A"
    return report

def check_discrete_mode(event):
    try:
        mode = int(event['configRuleName'].split("-")[1].split("_")[2])
        return mode
    except:
        return "All"

# This is the handler that's invoked by Lambda
def lambda_handler(event, context):
    global STS_SESSION
    global RESULT_TOKEN
    if "resultToken" in event:
        RESULT_TOKEN = event["resultToken"]

    rule_parameters = {}
    if 'ruleParameters' in event:
        if "RoleToAssume" not in event['ruleParameters']:
            return "Error: Missing the parameter named RoleToAssume"
        rule_parameters = json.loads(event['ruleParameters'])
    else:
        return "Error: Missing the parameter named RoleToAssume"

    STS_SESSION = get_sts_session(event, rule_parameters["RoleToAssume"])

    # Initiate depending if the Rule has been deployed in Discrete mode or not.

    DiscreteModeRule = check_discrete_mode(event)

    if DiscreteModeRule == 1 or DiscreteModeRule == "All":
        IAM_1_1_root_no_access()

    if DiscreteModeRule == 2 or DiscreteModeRule == "All":
        IAM_1_2_user_mfa_enabled(event)

    if DiscreteModeRule == 12 or DiscreteModeRule == "All":
        IAM_1_12_root_no_access_key()

    if DiscreteModeRule == 13 or DiscreteModeRule == "All":
        IAM_1_13_root_mfa_enabled()

    if DiscreteModeRule == 14 or DiscreteModeRule == "All":
        IAM_1_14_root_hardware_mfa()

    if DiscreteModeRule == 16 or DiscreteModeRule == "All":
        IAM_1_16_iam_policies_only_group_roles(event)

    if DiscreteModeRule == 21 or DiscreteModeRule == "All":
        IAM_1_21_instance_role_use(event)

    if DiscreteModeRule == 24 or DiscreteModeRule == "All":
        IAM_1_24_iam_policy_no_full_star()
