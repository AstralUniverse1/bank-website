provider "aws" {
  region = "ap-northeast-1"
}

resource "aws_instance" "vm" {
  ami           = "ami-03873003744ddc492"
  instance_type = "t3.micro"

  tags = {
    Name = "bank-terraform-vm"
  }
}
