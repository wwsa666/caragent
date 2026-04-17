from rag.rag_service import RagSummarizeService
if __name__ == '__main__':
    r=RagSummarizeService()
    print(r.rag_summarize("新能源车在零下5度应该怎么保养电池"))