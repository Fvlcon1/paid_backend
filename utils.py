from fastapi import UploadFile  # Add this import statement
import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
from scipy.spatial.distance import cosine, euclidean
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import requests
from io import BytesIO

class FaceComparisonSystem:
    def __init__(self, model_name: str = "buffalo_l", det_size: Tuple[int, int] = (640, 640)):
        """
        Initialize the face comparison system
        
        Args:
            model_name: Name of the InsightFace model to use
            det_size: Detection size for face analysis
        """
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        self.app = FaceAnalysis(name=model_name)
        self.app.prepare(ctx_id=0, det_size=det_size)
        
    def process_image(self, image_path: str) -> np.ndarray:
        """Process an image and return the RGB array"""
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    def get_face_info(self, image: np.ndarray, require_single_face: bool = False) -> List[Dict]:
        """Extract face information including embeddings and scores"""
        faces = self.app.get(image)
        
        if len(faces) == 0:
            raise ValueError("No faces detected in image")
            
        if require_single_face and len(faces) > 1:
            raise ValueError("Multiple faces detected in image when only one was expected")
        
        face_info = []
        for face in faces:
            info = {
                'bbox': face.bbox.tolist(),
                'embedding': face.embedding,
                'detection_score': face.det_score,
                'facial_features': {
                    'norm_l2': float(np.linalg.norm(face.embedding)),
                    'bbox_area': float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])),
                    'bbox_aspect_ratio': float((face.bbox[2] - face.bbox[0]) / (face.bbox[3] - face.bbox[1]))
                }
            }
            face_info.append(info)
            
        return face_info

    def calculate_similarity_metrics(self, emb1: np.ndarray, emb2: np.ndarray) -> Dict[str, float]:
        """Calculate various similarity metrics between two embeddings"""
        cosine_sim = 1 - cosine(emb1, emb2)
        euclidean_dist = euclidean(emb1, emb2)
        
        # Normalize embeddings for additional metrics
        norm_emb1 = emb1 / np.linalg.norm(emb1)
        norm_emb2 = emb2 / np.linalg.norm(emb2)
        
        # Additional similarity metrics
        dot_product = np.dot(norm_emb1, norm_emb2)
        manhattan_dist = np.sum(np.abs(norm_emb1 - norm_emb2))
        
        return {
            'cosine_similarity': float(cosine_sim),
            'euclidean_distance': float(euclidean_dist),
            'normalized_dot_product': float(dot_product),
            'manhattan_distance': float(manhattan_dist)
        }

    def compare_faces(self, img1: np.ndarray, img2: np.ndarray, threshold: float = 0.5) -> Dict:
        """
        Perform detailed face comparison between two images
        
        Args:
            img1: First image as a numpy array
            img2: Second image as a numpy array
            threshold: Similarity threshold for considering faces a match
            
        Returns:
            Dictionary containing detailed comparison results
        """
        try:
            # Get face information
            face1_info = self.get_face_info(img1, require_single_face=True)[0]
            face2_info = self.get_face_info(img2, require_single_face=True)[0]
            
            # Calculate similarity metrics
            similarity_metrics = self.calculate_similarity_metrics(
                face1_info['embedding'],
                face2_info['embedding']
            )
            
            # Primary similarity score (cosine similarity)
            similarity = similarity_metrics['cosine_similarity']
            
            results = {
                'match_summary': {
                    'is_match': similarity > threshold,
                    'similarity_score': similarity,
                    'confidence': float(face1_info['detection_score'] * face2_info['detection_score']),
                    'threshold_used': threshold
                },
                'detailed_analysis': {
                    'similarity_metrics': similarity_metrics,
                    'face_geometry': {
                        'size_ratio': face1_info['facial_features']['bbox_area'] / face2_info['facial_features']['bbox_area'],
                        'aspect_ratio_difference': abs(face1_info['facial_features']['bbox_aspect_ratio'] - 
                                                    face2_info['facial_features']['bbox_aspect_ratio'])
                    }
                },
                'face1_details': {
                    'detection_score': float(face1_info['detection_score']),
                    'bbox': face1_info['bbox'],
                    'facial_features': face1_info['facial_features']
                },
                'face2_details': {
                    'detection_score': float(face2_info['detection_score']),
                    'bbox': face2_info['bbox'],
                    'facial_features': face2_info['facial_features']
                },
                'metadata': {
                    'timestamp': datetime.now().isoformat()
                }
            }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error comparing faces: {str(e)}")
            raise

    async def compare_blobs(self, profile_image_url: str, webcam_image: UploadFile, threshold: float = 0.5) -> Dict:
        """Compare two image blobs"""
        try:
            # Fetch the profile image from the URL
            response = requests.get(profile_image_url)
            if response.status_code != 200:
                raise ValueError(f"Failed to fetch profile image from URL: {profile_image_url}")

            # Convert the fetched image to a numpy array
            member_image_data = BytesIO(response.content)
            member_image_np = np.frombuffer(member_image_data.getvalue(), np.uint8)
            member_image_cv = cv2.imdecode(member_image_np, cv2.IMREAD_COLOR)
            member_image_rgb = cv2.cvtColor(member_image_cv, cv2.COLOR_BGR2RGB)

            # Read the uploaded webcam image
            webcam_image_data = await webcam_image.read()
            webcam_image_np = np.frombuffer(webcam_image_data, np.uint8)
            webcam_image_cv = cv2.imdecode(webcam_image_np, cv2.IMREAD_COLOR)
            webcam_image_rgb = cv2.cvtColor(webcam_image_cv, cv2.COLOR_BGR2RGB)

            # Compare faces
            return self.compare_faces(member_image_rgb, webcam_image_rgb, threshold)
        except Exception as e:
            self.logger.error(f"Error in compare_blobs: {str(e)}")
            raise

    def batch_compare(self, target_image: str, comparison_images: List[str], 
                     threshold: float = 0.5) -> List[Dict]:
        """Compare one face against multiple other faces"""
        results = []
        
        try:
            for comp_image in comparison_images:
                try:
                    comparison = self.compare_faces(target_image, comp_image, threshold)
                    results.append({
                        'comparison_image': comp_image,
                        **comparison
                    })
                except Exception as e:
                    self.logger.warning(f"Failed to compare with {comp_image}: {str(e)}")
                    continue
            
            results.sort(key=lambda x: x['match_summary']['similarity_score'], reverse=True)
            return results
            
        except Exception as e:
            self.logger.error(f"Error in batch comparison: {str(e)}")
            raise

def main():
    # Initialize the system
    face_system = FaceComparisonSystem()
    
    # Compare faces
    print("\nComparing two faces:")
    comparison = face_system.compare_faces("face1.jpeg", "face2.jpg", threshold=0.5)
    
    # Print results
    print("\nMatch Summary:")
    print(f"Is Match: {comparison['match_summary']['is_match']}")
    print(f"Similarity Score: {comparison['match_summary']['similarity_score']:.4f}")
    print(f"Confidence: {comparison['match_summary']['confidence']:.4f}")
    
    print("\nDetailed Similarity Metrics:")
    metrics = comparison['detailed_analysis']['similarity_metrics']
    for metric, value in metrics.items():
        print(f"{metric}: {value:.4f}")
    
    print("\nFace Geometry Analysis:")
    geometry = comparison['detailed_analysis']['face_geometry']
    print(f"Size Ratio: {geometry['size_ratio']:.4f}")
    print(f"Aspect Ratio Difference: {geometry['aspect_ratio_difference']:.4f}")

if __name__ == "__main__":
    main()