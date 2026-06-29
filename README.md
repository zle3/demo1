# gcp vpc and networking

quick demo project showcasing terraform in gcp to create a vpc

link to demo site below:

[demo1.zachle.info](https://demo1.zachle.info)

## what's included

public + private subnets

cloud router + nat

firewall rule for iap ssh access only, no exposed ports

vpc logging

compute engine vm, for comparison against cloud run

dedicated service account for the vm, scoped to artifact registry read only

## setup

authentication handled by service account "terraform-deployer" with least privilege

state stored in gcs bucket with versioning

gitignored state, tfvars, and key files

docker image built and pushed to artifact registry

sample docker python application hosted on cloud run

gcp load balancer enabled

ssl certificate from google with a full strict tls cloudflare proxy

dns hosted on cloudflare

website front end with gcp/cloudflare verification checks

## TODO

CI/CD workflows

cloudflare DNS/WAF integration
