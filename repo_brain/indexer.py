"""Repository indexer for file scanning, symbol extraction, and git analysis."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .exceptions import IndexingError, TreeSitterError, GitAnalysisError
from .models import FileMetadata, Symbol

logger = logging.getLogger(__name__)


class RepoIndexer:
    """Indexes repository files, extracts symbols, and analyzes git history."""
    
    EXTENSION_TO_LANGUAGE = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".cs": "csharp",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
    }
    
    EXCLUDE_PATTERNS = {
        ".git", "node_modules", "venv", "__pycache__", ".pytest_cache",
        "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
        ".venv", "env", ".tox", "coverage", ".coverage", "htmlcov",
        ".idea", ".vscode", ".DS_Store", "*.pyc", "*.pyo", "*.pyd",
        ".egg-info", "*.so", "*.dylib", "*.dll", "*.exe",
    }
    
    DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc", ".textile"}
    DOC_PATTERNS = {"readme", "changelog", "contributing", "license", "docs/"}
    
    def __init__(self, repo_path: str, config: dict, llm_client):
        """Initialize the indexer.
        
        Args:
            repo_path: Path to the repository
            config: RAG configuration
            llm_client: LLM client for embeddings
        """
        self.repo_path = Path(repo_path)
        self.config = config
        self.llm_client = llm_client
        self.parsers = {}
        self.git_repo = None
        
        self._initialize_parsers()
        self._initialize_git_repo()
    
    def _initialize_parsers(self):
        """Initialize tree-sitter parsers for supported languages."""
        try:
            from tree_sitter import Language, Parser
            
            # Python
            try:
                import tree_sitter_python as tspython
                py_lang = Language(tspython.language())
                py_parser = Parser(py_lang)
                self.parsers["python"] = py_parser
                logger.debug("Initialized Python parser")
            except Exception as e:
                logger.warning(f"Failed to initialize Python parser: {e}")
            
            # JavaScript
            try:
                import tree_sitter_javascript as tsjavascript
                js_lang = Language(tsjavascript.language())
                js_parser = Parser(js_lang)
                self.parsers["javascript"] = js_parser
                logger.debug("Initialized JavaScript parser")
            except Exception as e:
                logger.warning(f"Failed to initialize JavaScript parser: {e}")
            
            # TypeScript
            try:
                import tree_sitter_typescript as tstypescript
                ts_lang = Language(tstypescript.language_typescript())
                ts_parser = Parser(ts_lang)
                self.parsers["typescript"] = ts_parser
                logger.debug("Initialized TypeScript parser")
            except Exception as e:
                logger.warning(f"Failed to initialize TypeScript parser: {e}")
            
            # Java
            try:
                import tree_sitter_java as tsjava
                java_lang = Language(tsjava.language())
                java_parser = Parser(java_lang)
                self.parsers["java"] = java_parser
                logger.debug("Initialized Java parser")
            except Exception as e:
                logger.warning(f"Failed to initialize Java parser: {e}")
            
            # C#
            try:
                import tree_sitter_c_sharp as tscsharp
                csharp_lang = Language(tscsharp.language())
                csharp_parser = Parser(csharp_lang)
                self.parsers["csharp"] = csharp_parser
                logger.debug("Initialized C# parser")
            except Exception as e:
                logger.warning(f"Failed to initialize C# parser: {e}")
            
            # Go
            try:
                import tree_sitter_go as tsgo
                go_lang = Language(tsgo.language())
                go_parser = Parser(go_lang)
                self.parsers["go"] = go_parser
                logger.debug("Initialized Go parser")
            except Exception as e:
                logger.warning(f"Failed to initialize Go parser: {e}")
            
            # Rust
            try:
                import tree_sitter_rust as tsrust
                rust_lang = Language(tsrust.language())
                rust_parser = Parser(rust_lang)
                self.parsers["rust"] = rust_parser
                logger.debug("Initialized Rust parser")
            except Exception as e:
                logger.warning(f"Failed to initialize Rust parser: {e}")
            
            # C
            try:
                import tree_sitter_c as tsc
                c_lang = Language(tsc.language())
                c_parser = Parser(c_lang)
                self.parsers["c"] = c_parser
                logger.debug("Initialized C parser")
            except Exception as e:
                logger.warning(f"Failed to initialize C parser: {e}")
            
            # C++
            try:
                import tree_sitter_cpp as tscpp
                cpp_lang = Language(tscpp.language())
                cpp_parser = Parser(cpp_lang)
                self.parsers["cpp"] = cpp_parser
                logger.debug("Initialized C++ parser")
            except Exception as e:
                logger.warning(f"Failed to initialize C++ parser: {e}")
                
        except ImportError as e:
            logger.warning(f"tree-sitter not available: {e}")
    
    def _initialize_git_repo(self):
        """Initialize GitPython repo object."""
        try:
            import git
            self.git_repo = git.Repo(self.repo_path)
            logger.debug(f"Initialized git repo: {self.repo_path}")
        except Exception as e:
            logger.warning(f"Failed to initialize git repo: {e}")
            self.git_repo = None
    
    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded."""
        path_str = str(path)
        for pattern in self.EXCLUDE_PATTERNS:
            if pattern in path_str or path.name == pattern:
                return True
        return False
    
    def _detect_language(self, file_path: Path) -> Optional[str]:
        """Detect language from file extension."""
        return self.EXTENSION_TO_LANGUAGE.get(file_path.suffix)
    
    def _is_documentation(self, file_path: Path) -> bool:
        """Check if file is documentation."""
        if file_path.suffix in self.DOC_EXTENSIONS:
            return True
        path_lower = str(file_path).lower()
        return any(pattern in path_lower for pattern in self.DOC_PATTERNS)
    
    def _is_binary(self, file_path: Path) -> bool:
        """Check if file is binary."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
                return b"\x00" in chunk
        except Exception:
            return True
    
    async def scan_repository(
        self, progress_callback: Optional[Callable] = None
    ) -> List[FileMetadata]:
        """Scan repository and collect file metadata.
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of FileMetadata objects
        """
        logger.info(f"Scanning repository: {self.repo_path}")
        files_metadata = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            scan_task = progress.add_task("Scanning files...", total=None)
            
            all_files = []
            for file_path in self.repo_path.rglob("*"):
                if file_path.is_file() and not self._should_exclude(file_path):
                    all_files.append(file_path)
            
            progress.update(scan_task, total=len(all_files))
            
            for idx, file_path in enumerate(all_files):
                try:
                    if self._is_binary(file_path):
                        logger.debug(f"Skipping binary file: {file_path}")
                        continue
                    
                    language = self._detect_language(file_path)
                    if not language and not self._is_documentation(file_path):
                        continue
                    
                    relative_path = file_path.relative_to(self.repo_path)
                    stat = file_path.stat()
                    
                    git_info = await self.analyze_git_history(str(relative_path))
                    
                    metadata = FileMetadata(
                        file_path=str(relative_path),
                        language=language or "markdown",
                        size_bytes=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                        git_last_commit=git_info.get("last_commit"),
                        git_commit_count=git_info.get("commit_count", 0),
                        is_documentation=self._is_documentation(file_path),
                    )
                    files_metadata.append(metadata)
                    
                    if progress_callback:
                        progress_callback(idx + 1, len(all_files))
                    
                except Exception as e:
                    logger.warning(f"Failed to process file {file_path}: {e}")
                finally:
                    progress.update(scan_task, advance=1)
        
        logger.info(f"Scanned {len(files_metadata)} files")
        return files_metadata
    
    async def extract_symbols(self, file_path: str, language: str) -> List[Symbol]:
        """Extract symbols from a file.
        
        Args:
            file_path: Path to the file
            language: Programming language
            
        Returns:
            List of Symbol objects
        """
        if language not in self.parsers:
            logger.debug(f"No parser available for {language}")
            return []
        
        try:
            full_path = self.repo_path / file_path
            with open(full_path, "rb") as f:
                content = f.read()
            
            parser = self.parsers[language]
            tree = parser.parse(content)
            
            symbols = []
            self._extract_symbols_from_node(
                tree.root_node, content, file_path, symbols
            )
            
            logger.debug(f"Extracted {len(symbols)} symbols from {file_path}")
            return symbols
            
        except Exception as e:
            logger.warning(f"Failed to extract symbols from {file_path}: {e}")
            return []
    
    def _extract_symbols_from_node(
        self, node, content: bytes, file_path: str, symbols: List[Symbol], scope: str = None
    ):
        """Recursively extract symbols from tree-sitter node."""
        symbol_types = {
            "function_definition": "function",
            "function_declaration": "function",
            "method_definition": "method",
            "class_definition": "class",
            "class_declaration": "class",
            "interface_declaration": "interface",
            "type_alias_declaration": "type",
            "enum_declaration": "enum",
        }
        
        if node.type in symbol_types:
            name_node = None
            for child in node.children:
                if child.type in ("identifier", "property_identifier", "type_identifier"):
                    name_node = child
                    break
            
            if name_node:
                name = content[name_node.start_byte:name_node.end_byte].decode("utf-8")
                signature = content[node.start_byte:node.end_byte].decode("utf-8")
                
                # Limit signature length
                if len(signature) > 200:
                    signature = signature[:200] + "..."
                
                symbol = Symbol(
                    name=name,
                    type=symbol_types[node.type],
                    file_path=file_path,
                    line_number=node.start_point[0] + 1,
                    scope=scope,
                    signature=signature.split("\n")[0],
                )
                symbols.append(symbol)
                
                # Update scope for nested symbols
                new_scope = f"{scope}.{name}" if scope else name
                for child in node.children:
                    self._extract_symbols_from_node(
                        child, content, file_path, symbols, new_scope
                    )
                return
        
        for child in node.children:
            self._extract_symbols_from_node(child, content, file_path, symbols, scope)
    
    async def analyze_git_history(self, file_path: str) -> Dict:
        """Analyze git history for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with git information
        """
        if not self.git_repo:
            return {"commit_count": 0, "last_commit": None, "last_modified": None}
        
        try:
            commits = list(self.git_repo.iter_commits(paths=file_path, max_count=100))
            
            if commits:
                return {
                    "commit_count": len(commits),
                    "last_commit": commits[0].hexsha[:8],
                    "last_modified": datetime.fromtimestamp(commits[0].committed_date),
                }
            else:
                return {"commit_count": 0, "last_commit": None, "last_modified": None}
                
        except Exception as e:
            logger.debug(f"Failed to analyze git history for {file_path}: {e}")
            return {"commit_count": 0, "last_commit": None, "last_modified": None}
    
    async def get_hot_files(self, top_n: int = 20) -> List[str]:
        """Get frequently modified files (hot files).
        
        Args:
            top_n: Number of hot files to return
            
        Returns:
            List of file paths
        """
        if not self.git_repo:
            return []
        
        try:
            since_date = datetime.now() - timedelta(days=90)
            commits = self.git_repo.iter_commits(since=since_date)
            
            file_changes = {}
            for commit in commits:
                for item in commit.stats.files:
                    file_changes[item] = file_changes.get(item, 0) + 1
            
            sorted_files = sorted(
                file_changes.items(), key=lambda x: x[1], reverse=True
            )
            
            return [f[0] for f in sorted_files[:top_n]]
            
        except Exception as e:
            logger.warning(f"Failed to get hot files: {e}")
            return []
