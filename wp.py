import sqlite3
import sys
import json
import natto
import math
import numpy as np

class Document():
    """Abstract class representing a document.
    """

    def id(self):
        """Returns the id for the Document. Should be unique within the Collection.
        """
        raise NotImplementedError()

    def text(self):
        """Returns the text for the Document.
        """
        raise NotImplementedError()

class Collection():
    """Abstract class representing a collection of documents.
    """

    def get_document_by_id(self, id):
        """Gets the document for the given id.

        Returns:
            Document: The Document for the given id.
        """
        raise NotImplementedError()

    def num_documents(self):
        """Returns the number of documents.

        Returns:
            int: The number of documents in the collection.
        """
        raise NotImplementedError()

    def get_all_documents(self):
        """Creates an iterator that iterates through all documents in the collection.

        Returns:
            Iterable[Document]: All the documents in the collection.
        """
        raise NotImplementedError()

class WikipediaArticle(Document):
    """A Wikipedia article.

    Attributes:
        title (str): The title. This will be unique so it can be used as the id. It will also always be less than 256 bytes.
        _text (str): The plain text version of the article body.
        opening_text (str): The first paragraph of the article body.
        auxiliary_text (List[str]): A list of auxiliary text, usually from the inbox.
        categories (List[str]): A list of categories.
        headings (List[str]): A list of headings (i.e. the table of contents).
        wiki_text (str): The MediaWiki markdown source.
        popularity_score(float): Some score indicating article popularity. Bigger is more popular.
        num_incoming_links(int): Number of links (within Wikipedia) that point to this article.
    """
    def __init__(self, collection, title, text, opening_text, auxiliary_text, categories, headings, wiki_text, popularity_score, num_incoming_links):
        self.title = title
        self._text = text
        self.opening_text = opening_text
        self.auxiliary_text = auxiliary_text # list
        self.categories = categories
        self.headings = headings
        self.wiki_text = wiki_text
        self.popularity_score = popularity_score
        self.num_incoming_links = num_incoming_links

    def id(self):
        """Returns the id for the WikipediaArticle, which is its title.

        Override for Document.

        Returns:
            str: The id, which in the Wikipedia article's case, is the title.
        """
        return self.title

    def text(self):
        """Returns the text for the Document.

        Override for Document.

        Returns:
            str: Text for the Document
        """
        return self._text

class WikipediaCollection(Collection):
    """A collection of WikipediaArticles.
    """
    def __init__(self, filename):
        self._cached_num_documents = None
        self.db = sqlite3.connect(filename)

    def find_article_by_title(self, query):
        """Finds an article with a title matching the query.

        Returns:
            WikipediaArticle: Returns matching WikipediaArticle.
        """
        c = self.db.cursor()
        row = c.execute("SELECT title, text, opening_text, auxiliary_text, categories, headings, wiki_text, popularity_score, num_incoming_links FROM articles WHERE title=?", (query,)).fetchone()
        if row is None:
            return None
        return WikipediaArticle(self,
            row[0], # title
            row[1], # text
            row[2], # opening_text
            json.loads(row[3]), # auxiliary_text
            json.loads(row[4]), # categories
            json.loads(row[5]), # headings
            row[6], # wiki_text
            row[7], # popularity_score
            row[8], # num_incoming_links
        )

    def get_document_by_id(self, doc_id):
        """Gets the document (i.e. WikipediaArticle) for the given id (i.e. title).

        Override for Collection.

        Returns:
            WikipediaArticle: The WikipediaArticle for the given id.
        """
        c = self.db.cursor()
        row = c.execute("SELECT text, opening_text, auxiliary_text, categories, headings, wiki_text, popularity_score, num_incoming_links FROM articles WHERE title=?", (doc_id,)).fetchone()
        if row is None:
            return None
        return WikipediaArticle(self, doc_id,
            row[0], # text
            row[1], # opening_text
            json.loads(row[2]), # auxiliary_text
            json.loads(row[3]), # categories
            json.loads(row[4]), # headings
            row[5], # wiki_text
            row[6], # popularity_score
            row[7], # num_incoming_links
        )

    def num_documents(self):
        """Returns the number of documents (i.e. WikipediaArticle).

        Override for Collection.

        Returns:
            int: The number of documents in the collection.
        """
        if self._cached_num_documents is None:
            c = self.db.cursor()
            num_documents = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            self._cached_num_documents = num_documents
        return self._cached_num_documents

    def get_all_documents(self):
        """Creates an iterator that iterates through all documents (i.e. WikipediaArticles) in the collection.

        Returns:
            Iterable[WikipediaArticle]: All the documents in the collection.
        """
        c = self.db.cursor()
        c.execute("SELECT title, text, opening_text, auxiliary_text, categories, headings, wiki_text, popularity_score, num_incoming_links FROM articles")
        BLOCK_SIZE = 1000
        while True:
            block = c.fetchmany(BLOCK_SIZE)
            if len(block) == 0:
                break
            for row in block:
                yield WikipediaArticle(self,
                    row[0], # title
                    row[1], # text
                    row[2], # opening_text
                    json.loads(row[3]), # auxiliary_text
                    json.loads(row[4]), # categories
                    json.loads(row[5]), # headings
                    row[6], # wiki_text
                    row[7], # popularity_score
                    row[8], # num_incoming_links
                )

class Index():
   """
   Arguments:
       filename: location of sqlite db
       collection: Collection to index and search
   """
   def __init__(self, filename, collection):
       self.db = sqlite3.connect(filename)
       self.collection = collection

   """Searches the index for documents that match the query.

   Returns:
       list: list of matching document ids
   """
   def search(self, query):
       parser = natto.MeCab()
       set_return_goal = set([])
       terms = []
       for node in parser.parse(query, as_nodes=True):
           # print(node)
           print(node.surface)
           if node.is_nor():
               features = node.feature.split(',')
               print(node.surface)
               if features[0] == '名詞':
                   #node.surface  # これが探すキーワード(=term)
                   c = self.db.cursor()
                   # query をみて termsを listでもらう
                   terms.append(node.surface)

                   # andをとった結果のgoalsを listでもらう:set_return_goal
                   sub_goal = c.execute("SELECT document_id FROM postings WHERE term = ?", (node.surface,)).fetchall()
                   # とりあえず保留でand取るか
                   goal = []
                   for num in sub_goal:
                        goal.append(num[0])
                        # numはtupleなのでlist
                   if not set_return_goal:
                       set_return_goal = set(goal)
                   else:
                       set_return_goal = set(goal) & set_return_goal

       # 類似度の計算
       v_q = np.array(self.calc_tf(query,terms)) * np.array(self.calc_idf(terms))
       v_q = np.array(v_q)
       v_docs = []
       print (set_return_goal)
       for candi_id in set_return_goal:
           print "hi"
           print(candi_id)
           v_docs.append(np.array(self.calc_tf(candi_id,terms)) * np.array(self.calc_idf(terms)))
       cos_theta = []
       for v_doc in v_docs:
           v_doc = np.array(v_doc)
           theta = np.dot(v_q,v_doc) / np.linalg.norm(v_q) / np.linalg.norm(v_doc)
           cos_theta.append(theta)
       print (terms[0])
       print (v_docs)
       max_index = cos_theta.index(max(cos_theta))
       return goal[max_index]

   def calc_tf(self,doc,terms):
       parser = natto.MeCab()
       tf = [0 for i in range(len(terms))]
       for node in parser.parse(doc,as_nodes = True):
           i = 0
           for term in terms:
               if node.surface == term:
                   tf[i] += 1
               i += 1
       return tf

   def calc_idf(self,terms):
           idf = [0 for i in range(len(terms))]
           N = self.collection.num_documents()
           i = 0
           for i in range(len(terms)):
               # df = self.cal_df(terms[i])
               df = 3
               idf[i] = math.log(N / df)
           return idf

   def cal_df(self,term):
        # input:term
        # output:document_id数

        c = self.db.cursor()
        sub_goal = c.execute("SELECT document_id from postings where term = ?", (term,)).fetchall()
        # ここは必要?
        goal = []
        for num in sub_goal:
            goal.append(num[0])
        # ここは必要?
        return len(goal)

   def generate(self):
       self.db.executescript("""
       CREATE TABLE IF NOT EXISTS postings (
           term TEXT NOT NULL,
           document_id TEXT NOT NULL
       );
       """)
       parser = natto.MeCab()
       i = 0
       for wiki_article in self.collection.get_all_documents():
           if i > 10:
               break
           i += 1
           # print(wiki_article._text)
           for node in parser.parse(wiki_article._text, as_nodes=True):
               # print(node)
               if node.is_nor():
                   features = node.feature.split(',')
                   if features[0] == '名詞':
                       c = self.db.cursor()
                       # c = self.db.cursor()
                       # row = c.execute("SELECT text, opening_text, auxiliary_text, categories, headings, wiki_text, popularity_score, num_incoming_links FROM articles WHERE title=?", (doc_id,)).fetchone()
                       c.execute("INSERT into postings (term, document_id) values (?, ?)", (node.surface, wiki_article.title))
                       self.db.commit()
       self.db.executescript("""
       CREATE INDEX IF NOT EXISTS my_index on postings (
           term, document_id
           );
       """)
