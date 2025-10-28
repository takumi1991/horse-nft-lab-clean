terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30.0"
    }
  }
}

  cloud {
    organization = "YOUR_TERRAFORM_CLOUD_ORG"  # Terraform Cloud上のOrganization名
    workspaces {
      name = "horse-nft-lab-clean"
    }
  }
}

provider "google" {
  project = "horse-nft-lab-clean"
  region  = "asia-northeast1"
}
