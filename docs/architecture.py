"""Architecture diagram for aws-rag-quality-gate-starter.

Render:  pip install diagrams   (also needs Graphviz: apt install graphviz / brew install graphviz)
         python docs/architecture.py   ->  docs/architecture.png (written next to this script)
"""
import os

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import RDSPostgresqlInstance
from diagrams.aws.general import User
from diagrams.aws.integration import SimpleNotificationServiceSns
from diagrams.aws.management import Cloudwatch
from diagrams.aws.ml import Bedrock
from diagrams.aws.network import APIGateway
from diagrams.aws.security import SecretsManager
from diagrams.aws.storage import SimpleStorageServiceS3

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "architecture")

FONT = "DejaVu Sans"
GRAPH = {
    "fontname": FONT, "fontsize": "28", "labelloc": "t", "pad": "0.5",
    "nodesep": "0.6", "ranksep": "1.0", "splines": "spline",
}
NODE = {"fontname": FONT, "fontsize": "18", "imagepos": "tc"}
EDGE = {"fontname": FONT, "fontsize": "16", "color": "#555555"}

with Diagram(
    "AWS RAG Quality Gate Architecture",
    filename=OUT, outformat="png", show=False,
    graph_attr=GRAPH, node_attr=NODE, edge_attr=EDGE,
):
    user = User("Developer")
    engineer = User("Engineer\n(API client)")

    with Cluster("AWS Account", graph_attr={"bgcolor": "#f0f0f0"}):
        
        with Cluster("Ingestion Pipeline"):
            docs_bucket = SimpleStorageServiceS3("Documents\nBucket\n(PDF uploads)")
            ingest_lambda = Lambda("Ingest\nLambda")
            
        with Cluster("Vector Database"):
            aurora = RDSPostgresqlInstance("Aurora\nPostgreSQL\nServerless v2\n(pgvector)")
            secrets = SecretsManager("Secrets\nManager\n(DB creds)")
        
        with Cluster("Query API"):
            api = APIGateway("API Gateway\nHTTP API")
            query_lambda = Lambda("Query\nLambda")
        
        with Cluster("Foundation Models"):
            bedrock = Bedrock("Amazon\nBedrock\n(Titan + Claude)")
        
        with Cluster("Observability"):
            cloudwatch = Cloudwatch("CloudWatch\nMetrics + Logs\n+ Dashboard")
    
    user >> Edge(label="1. Upload PDF") >> docs_bucket
    docs_bucket >> Edge(label="S3 trigger") >> ingest_lambda
    ingest_lambda >> Edge(label="extract, chunk,\nembed") >> bedrock
    ingest_lambda >> Edge(label="store vectors") >> aurora
    
    secrets >> Edge(label="credentials", style="dashed") >> ingest_lambda
    secrets >> Edge(label="credentials", style="dashed") >> query_lambda
    
    engineer >> Edge(label="2. POST /query") >> api
    api >> Edge(label="invoke") >> query_lambda
    query_lambda >> Edge(label="embed question") >> bedrock
    query_lambda >> Edge(label="retrieve chunks\n(vector search)") >> aurora
    query_lambda >> Edge(label="generate answer\nwith citations") >> bedrock
    query_lambda >> Edge(label="JSON response") >> api
    api >> Edge(label="answer +\ncitations") >> engineer
    
    ingest_lambda >> Edge(label="logs + metrics", style="dotted") >> cloudwatch
    query_lambda >> Edge(label="logs + metrics", style="dotted") >> cloudwatch
