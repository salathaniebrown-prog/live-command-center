terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
resource "aws_instance" "astra_gpu_node" {
  ami           = "ami-0c7217cdde317cfec"
  instance_type = "g5.xlarge"
  tags = { Name = "ASTRA-GPU-Datacenter-Node", ManagedBy = "ASTRA-8143" }
}
