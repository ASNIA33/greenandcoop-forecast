import boto3
import os
import logging
from botocore.exceptions import NoCredentialsError, ClientError


logger = logging.getLogger(__name__)

class S3Connector:
    def __init__(self):
        # Récupération des identifiants depuis le fichier .env
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "eu-west-3")
        )
    def download_files(self, local_dir: str = "data/raw"):
        """
        Télécharge tous les fichiers du bucket S3 vers un dossier local.
        """
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
        
        try:
            # A- Lister les objets dans le bucket
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)

            if "Contents" not in response:
                logger.info(f"Le bucket {self.bucket_name} est vide ou innaccessible.")
                return []

            download_files = []
            
            # B- Parcourir les objets et telecharger
            for obj in response["Contents"]:
                file_key = obj["Key"]

                # Ignorer les dossiers (clés finissant par /)
                if file_key.endswith("/"):
                    continue

                # On conserve juste le nom du fichier pour le stockage local
                filename = os.path.basename(file_key)
                local_path = os.path.join(local_dir, filename)

                logger.info(f"Téléchargement de {file_key} vers {local_path}")
                self.s3_client.download_file(self.bucket_name, file_key, local_path)
                download_files.append(filename)

            logger.info(f"Succès : {len(download_files)} fichiers telechargés depuis S3 vers {local_dir}")
            return download_files
        
        except NoCredentialsError:
            logger.info(f"Pas de crédentials trouvés pour accéder au bucket {self.bucket_name}.")
            raise
    
        except ClientError as e:
            logger.error(f"Erreur AWS S3 : {e}")
            raise