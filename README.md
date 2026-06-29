# gcp vpc and networking

quick demo project showcasing terraform in gcp to create a vpc

## what's included

public + private subnets

cloud router + NAT

firewall rule for IAP SSH access only, no exposed ports

vpc logging

## setup

authentication handled by service account "terraform-deployer" with least privilege

state stored in gcs bucket with versioning

## TODO

docker, VMs, load balancer

CI/CD workflows

cloudflare DNS/WAF integration
