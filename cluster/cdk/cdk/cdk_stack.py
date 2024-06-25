from aws_cdk import (
    Stack,
    Tags,
    CfnParameter,
    aws_eks as eks,
    aws_ec2 as ec2,
)
from constructs import Construct

class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Define the VPC
        vpc=ec2.Vpc(
            self,
            "eks_vpc",
            max_azs=3,
            nat_gateways=1,
            ip_addresses=ec2.IpAddresses.cidr("10.42.0.0/16"),
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=19,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=19,
                ),
            ],
        )
        
        Tags.of(vpc).add("kubernetes.io/role/elb", "1",
            include_resource_types=["AWS::EC2::Subnet::Public"],
        )
        
        # Create an EKS cluster
        cluster=eks.Cluster(
            self,
            "eks_cluster",
            cluster_name=self.node.try_get_context("cluster_name"),
            version=eks.KubernetesVersion.V1_29,
            vpc=vpc,
            default_capacity=0,  # We'll add the capacity through a managed node group
        )
        
        # Add the VPC CNI EKS addon
        vpc_cni_addon=eks.CfnAddon(
            self,
            "vpc_cni_addon",
            addon_name="vpc-cni",
            cluster_name=cluster.cluster_name,
            resolve_conflicts="OVERWRITE",
            configuration_values='{"env":{"ENABLE_PREFIX_DELEGATION":"true", "ENABLE_POD_ENI":"true", "POD_SECURITY_GROUP_ENFORCING_MODE":"standard"}}',
        )
        
        # Create a managed node group with 3 nodes (min 3, max 6) of m5.large instance type
        managed_node_group=cluster.add_nodegroup_capacity(
            id="managed_node_group",
            instance_types=[
                ec2.InstanceType(
                    "m5.large"
                )
            ],
            min_size=3,
            max_size=6,
            desired_size=3,
            subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            max_unavailable_percentage=50,
            labels={"workshop-default": "yes"}
        )