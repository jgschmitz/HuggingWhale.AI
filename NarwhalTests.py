import pytest
from unittest.mock import patch, MagicMock
from NarwalEmbeddings import NarwalEmbeddings

@patch("NarwalEmbeddings.MongoClient")
@patch("NarwalEmbeddings.SentenceTransformer")
def test_embed_and_store(mock_model_class, mock_mongo_client):
    # Mock the embedding model
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1, 0.2, 0.3]
    mock_model_class.return_value = mock_model

    # Mock the MongoDB client and collection
    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    mock_mongo_client.return_value.__getitem__.return_value = mock_db

    # Create instance with mocks
    narwal = NarwalEmbeddings("mongodb://fake-uri", "testdb", "testcol", model_name="fake-model")

    # Run the embed_and_store method
    result = narwal.embed_and_store("doc123", "The quick brown fox.")

    # Check embedding result
    assert result == [0.1, 0.2, 0.3]
    mock_model.encode.assert_called_once_with("The quick brown fox.")
    mock_collection.insert_one.assert_called_once_with({
        "_id": "doc123",
        "text": "The quick brown fox.",
        "embedding": [0.1, 0.2, 0.3]
    })

def test_init_sets_attributes():
    with patch("NarwalEmbeddings.MongoClient"), patch("NarwalEmbeddings.SentenceTransformer"):
        narwal = NarwalEmbeddings("uri", "db", "col", "model
