from UniTok import UniDep, Vocab

from typing import Optional

from torch import nn

from loader.embedding.embedding_loader import EmbeddingLoader, EmbeddingInfo
from utils.printer import printer


class TransformEmbedding(nn.Module):
    def __init__(self, embedding: nn.Embedding, from_dim: int, to_dim: int):
        super(TransformEmbedding, self).__init__()
        self.embedding = embedding
        self.linear = nn.Linear(from_dim, to_dim)

    def forward(self, indexes):
        return self.linear(self.embedding(indexes))


class EmbeddingInit:
    def __init__(
            self,
            order: list,
            depot: UniDep,
            hidden_size: int = 768,
            embedding_loader: EmbeddingLoader = None,
    ):
        self.print = printer.EMBEDDING__INIT_Cblue_
        self.order = order
        self.depot = depot
        self.hidden_size = hidden_size
        self.loader = embedding_loader

        self._table = None

    def register_vocab(self, vocab: Vocab):
        table = self.get_table()
        table[vocab.name] = nn.Embedding(
            num_embeddings=vocab.get_size(),
            embedding_dim=self.hidden_size,
        )

    def get_table(self) -> nn.ModuleDict:
        if self._table:
            return self._table

        vocabs = set()
        for col in self.order:
            vocabs.add(self.depot.get_vocab(col))

        table = dict()
        for vocab in vocabs:
            embedding_info = self.loader.get_embedding(vocab)  # type: Optional[EmbeddingInfo]
            expected_vocab_size = self.depot.get_vocab_size(vocab, as_vocab=True)

            if embedding_info and embedding_info.embedding:
                embedding = embedding_info.embedding
                is_frozen = "frozen" if embedding_info.frozen else "unfrozen"
                self.print(f'load {is_frozen} vocab: {vocab}, {embedding.shape}')

                if int(embedding.shape[0]) != expected_vocab_size:
                    raise ValueError(f'not meet the expected vocab size {expected_vocab_size}')

                table[vocab] = nn.Embedding.from_pretrained(embedding)
                table[vocab].weight.requires_grad = not embedding_info.frozen

                if int(embedding.shape[1]) != self.hidden_size:
                    self.print(f'transform hidden size from {int(embedding.shape[1])} to {self.hidden_size}')
                    table[vocab] = TransformEmbedding(
                        embedding=table[vocab],
                        from_dim=int(embedding.shape[1]),
                        to_dim=self.hidden_size
                    )
                continue

            self.print(f'create vocab {vocab}, ({expected_vocab_size}, {self.hidden_size})')
            table[vocab] = nn.Embedding(
                num_embeddings=expected_vocab_size,
                embedding_dim=self.hidden_size
            )
            # table[vocab].weight.requires_grad = True  # default

        return self._table

    @classmethod
    def parse(cls, data, model, depot):
        embedding_loader = EmbeddingLoader()
        for embedding_info in data.embedding:
            embedding_loader.append(**embedding_info.dict())

        return cls(
            order=data.order,
            depot=depot,
            hidden_size=model.config.hidden_size,
            embedding_loader=embedding_loader,
        )