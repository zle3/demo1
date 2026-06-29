# gcp vpc and networking

quick demo project showcasing terraform in gcp to create a vpc

link to demo site below:

[demo1.zachle.info](demo1.zachle.info)

## what's included

public + private subnets

cloud router + NAT

firewall rule for IAP SSH access only, no exposed ports

vpc logging

## setup

authentication handled by service account "terraform-deployer" with least privilege

state stored in gcs bucket with versioning

sample docker python application hosted on cloud run

ssl certificate from google with a full strict TLS cloudflare proxy

dns hosted on cloudflare

## TODO

docker, VMs, load balancer

CI/CD workflows

cloudflare DNS/WAF integration
