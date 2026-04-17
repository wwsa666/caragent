from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from rag.vector_store import VectorStoreService

from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model


class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def print_prompt(self,prompt):
        print(prompt.to_string())
        print("-"*20)
        return prompt


    def _init_chain(self):
        chain = self.prompt_template | self.print_prompt|self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)

    def rag_summarize(self, query: str) -> str:
        # print(query)

        context_docs = self.retriever_docs(query)
        # print(context_docs)
        # print("123456")

        context = ""
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"【参考资料{counter}】: 参考资料: {doc.page_content} | 参考元数据: {doc.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
            }
        )
if __name__ == '__main__':

    query="新能源车在零度以下环境下电池保养建议"
    rag = RagSummarizeService()

    print(rag.rag_summarize(query))