from recommender.engine import Policy, analyze
from recommender.repository import RecommendationRepository


class RecommendationService:
    def __init__(self, repository=None):
        self.repository = repository or RecommendationRepository()

    def analyze(self, batch_id, policy=None):
        bundle = self.repository.load(batch_id)
        result = analyze(bundle, policy or Policy())
        return self.repository.save(bundle, result)
