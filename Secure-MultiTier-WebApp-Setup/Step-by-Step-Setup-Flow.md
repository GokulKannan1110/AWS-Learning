# Secured Multi-Tier Web App Setup

## 1. IAM Setup

Create a user and add it to a user group.

### User Group
- `web-app-user-group`

Attach an IAM policy to the group.

### Role Created
- Role: `EC2-ReadOnly-S3Bucket-Role`
- Trusted entity: `AWS Service: ec2`

### IAM Policy
- Policy name: `EC2-ReadOnly-S3Bucket-RolePolicy`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyS3Bucket",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ReadOnlyS3Objects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## 2. Networking and Compute Layer Setup

### VPC and Subnets
- VPC: `vpc-02ebc534aff98fee6` / `webapp-vpc-01` - `10.1.0.0/16`
- Public subnet: `subnet-0e8a7d6ecb4c5dfec` / `webapp-public-subnet` - `10.1.10.0/24` - `ap-south-1a`
- Private subnet: `subnet-0b5ddc593c9d1be27` / `webapp-private-subnet` - `10.1.20.0/24`

### Network Components
- Internet Gateway: `igw-0e41d4459f00e35cf` / `webapp-ig`
- NAT Gateway: `nat-0c61a0f258fb0682a` / `webapp-nat-gateway` - created in the public subnet
- Public subnet route table: `rtb-07aa80b345675700b` / `webapp-public-rt` - routes `0.0.0.0/0` to Internet Gateway
- Private subnet route table: `rtb-0cfbca10b0b525854` / `webapp-private-rt` - routes `0.0.0.0/0` to NAT Gateway

### Security Groups
- Security Group 1: `sg-0390a088a5ac16c51` - `webapp-bastion-sg` - allows SSH from anywhere
- Security Group 2: `sg-089b46b3d12c6a6f6` - `private-sg` - allows SSH only from the bastion security group

### EC2 Instances
- Public EC2: `public-webapp-server` - `i-048263c7a840eae44`
  - Public IP: `15.206.173.221`
  - Private IP: `10.1.10.75`
- Private EC2: `private-backend-server` - `i-0f52775f7db41c5d6`
  - Private IP: `10.1.20.219`

---

## 3. SSH Access and EC2 Connection

### From Local Machine
```bash
chmod 400 webapp-server-keys.pem
ssh -i "webapp-server-keys.pem" ubuntu@15.206.173.221
```

### Copy PEM Key to Public EC2
```bash
scp -i webapp-server-keys.pem webapp-server-keys.pem ubuntu@15.206.173.221:~
```

### From Public EC2 to Private EC2
```bash
ssh -i webapp-server-keys.pem ubuntu@10.1.20.219
```

---

## 4. Docker Engine Installation on EC2 Instances

Run the following on both the public and private EC2 instances:

```bash
sudo apt update
sudo apt upgrade -y

sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

docker --version

sudo usermod -aG docker $USER
newgrp docker

docker ps
```

### Test Docker
```bash
docker run hello-world
```

---

## 5. PostgreSQL Setup in Private EC2

### Pull and Run PostgreSQL Container
```bash
docker pull postgres

docker volume create postgres_data

docker run -d \
  --name postgres \
  -e POSTGRES_USER=appuser \
  -e POSTGRES_PASSWORD=apppassword \
  -e POSTGRES_DB=appdb \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/ \
  postgres
```

> Note: For PostgreSQL 18+ and newer, the mount path should be `/var/lib/postgresql` instead of `/var/lib/postgresql/data`.

If the container exits quickly, inspect the logs:

```bash
docker logs postgres
```

If needed, remove and recreate the container and volume:

```bash
docker rm postgres
docker volume rm postgres_data
```

### Create Database Table
```bash
docker exec -it postgres psql -U appuser -d appdb

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    message TEXT NOT NULL
);
```

Check the table:

```sql
\dt
```

Insert sample data:

```sql
INSERT INTO messages (message)
VALUES
    ('Hello from PostgreSQL!'),
    ('This data is running inside a private EC2.'),
    ('FastAPI will retrieve this data.');

SELECT * FROM messages;
```

Exit PostgreSQL:

```sql
\q
```

---

## 6. Database Connectivity Check from Public EC2

From the public EC2, check TCP connectivity to the private EC2 PostgreSQL instance:

```bash
nc -vz 10.1.20.219 5432
```

If it does not work, the security group on the private instance must allow TCP traffic on port `5432` from the bastion/public security group.

### Required Security Group Rule
- Allow inbound TCP on port `5432` from `webapp-bastion-sg`

### Install PostgreSQL Client
```bash
sudo apt update
sudo apt install -y postgresql-client
```

### Connect to the Database
```bash
psql -h 10.1.20.219 -p 5432 -U appuser -d appdb
```

---

## 7. FastAPI Application Setup

Create the FastAPI app inside the public EC2 instance:

```bash
mkdir -p ~/fastapi-app
cd ~/fastapi-app
```

Create the `main.py`, `requirements.txt`, and `Dockerfile`, then build the image.

### Build and Run the Container
```bash
docker build -t my-fastapi-app .

docker run -d \
  --name fastapi \
  -p 8000:8000 \
  my-fastapi-app

docker ps
```

### Test the API
```bash
curl http://localhost:8000/
curl http://localhost:8000/messages
```

---

## 8. Nginx Frontend Setup

Use the default Nginx image and replace its default `index.html` with a page that calls the FastAPI API.

### Run Nginx Container
```bash
docker run -d \
  --name nginx \
  -p 80:80 \
  -v ~/nginx-app/html:/usr/share/nginx/html:ro \
  nginx
```

### Access the Application
Open the public IP of the EC2 instance:

```text
http://15.206.173.221
```

This will serve the HTML page on port `80`, and the browser will call the FastAPI app on port `8000`.

### Security Group Requirement
The public EC2 security group should allow both:
- Port `80` for Nginx
- Port `8000` for FastAPI API access

If only port `80` is open, the page loads but the API call fails.

---

## 9. Traffic Distribution Setup with Application Load Balancer

Create an Application Load Balancer in front of the public EC2 instance.

### Target Group
- Target group: `webapp-tg`
- Registered target: `public-webapp-server`

### ALB Setup
- Load balancer: `webapp-lb`

For high availability, the ALB should span multiple availability zones.

Because the original public subnet existed only in one AZ, create an additional public subnet in a different AZ.

### New Public Subnet
- `subnet-0a1e607bda03bb73c` / `webapp-subnet-az2`
- CIDR: `10.1.30.0/24`
- AZ: `ap-south-1b`

Both public subnets must route traffic to the Internet Gateway.

The ALB DNS name can then be used to reach the app:

```text
webapp-lb-315505965.ap-south-1.elb.amazonaws.com
```

### Architecture Overview
```text
VPC
├── AZ-a
│   ├── Public Subnet
│   │   └── Public EC2
│   └── Private Subnet
│       └── Private EC2 / PostgreSQL
└── AZ-b
    └── Public Subnet
```

```text
                 ALB
               /     \
             AZ-a     AZ-b
              |         |
        Public Subnet Public Subnet
              |
          Public EC2
              |
        Private EC2
         PostgreSQL
```

---

## 10. Visibility and Security Setup

### VPC Flow Logs
Enable VPC Flow Logs to inspect network traffic.

### CloudWatch Log Group
- Log group: `webapp-cw-flowlogs`

Create a role that allows Flow Logs to send data to CloudWatch.

### Role
- Role: `webapp-flowlogs-role`
- Trusted entity: `AWS Service: vpc-flow-logs`

### IAM Policy for Flow Logs
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Statement1",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "*"
    }
  ]
}
```

Then create the VPC Flow Log and point it to the CloudWatch log group.

- Flow log: `webapp-flowlogs` - `fl-0be1b22fe0af480eb`

Once enabled, you can inspect traffic logs by hitting the ALB URL or the EC2 public IP.

---

## 11. Security Setup

A WAF should be created and associated with the Application Load Balancer.

This is the first layer of protection that receives incoming requests. It can handle rules such as:
- Rate limiting
- IP allowlisting
- Request blocking based on patterns

This helps protect the application from common web attacks and unwanted traffic.

---

## Final Summary

This setup demonstrates a secure multi-tier AWS architecture with:
- A public-facing web layer
- A private backend layer
- A database isolated in a private subnet
- NAT-based private networking
- Security groups for controlled access
- ALB for traffic distribution
- VPC Flow Logs for visibility
- WAF for web protection

This architecture follows the core cloud security principle of isolating components and restricting access only to required resources.


