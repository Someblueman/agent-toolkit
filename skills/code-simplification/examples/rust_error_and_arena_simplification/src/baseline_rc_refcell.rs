//! Baseline Implementation: Graph using `Rc<RefCell<Node>>` and manual Error boilerplate.
//!
//! Problems demonstrated:
//! 1. Memory leaks when cyclic references exist (Rc cycles are not freed).
//! 2. Runtime panic hazards with `RefCell::borrow_mut()` during recursive graph traversals.
//! 3. Verbose manual `std::error::Error` and `Display` boilerplate.

use std::cell::RefCell;
use std::fmt;
use std::rc::Rc;

#[derive(Debug)]
pub enum GraphError {
    CycleDetected(String),
    NodeNotFound(String),
    BorrowConflict(String),
}

impl fmt::Display for GraphError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GraphError::CycleDetected(msg) => write!(f, "Cycle detected: {}", msg),
            GraphError::NodeNotFound(msg) => write!(f, "Node not found: {}", msg),
            GraphError::BorrowConflict(msg) => write!(f, "Borrow conflict: {}", msg),
        }
    }
}

impl std::error::Error for GraphError {}

pub struct Node {
    pub name: String,
    pub value: i64,
    pub dependencies: Vec<Rc<RefCell<Node>>>,
}

pub struct RcGraph {
    pub nodes: Vec<Rc<RefCell<Node>>>,
}

impl RcGraph {
    pub fn new() -> Self {
        Self { nodes: Vec::new() }
    }

    pub fn add_node(&mut self, name: &str, value: i64) -> Rc<RefCell<Node>> {
        let node = Rc::new(RefCell::new(Node {
            name: name.to_string(),
            value,
            dependencies: Vec::new(),
        }));
        self.nodes.push(Rc::clone(&node));
        node
    }

    pub fn add_dependency(from: &Rc<RefCell<Node>>, to: &Rc<RefCell<Node>>) {
        from.borrow_mut().dependencies.push(Rc::clone(to));
    }

    /// Evaluates total sum of reachable nodes, checking for cycles via visited set.
    pub fn evaluate_sum(&self, root: &Rc<RefCell<Node>>) -> Result<i64, GraphError> {
        let mut visited = Vec::new();
        let mut visiting = Vec::new();
        self.eval_recursive(root, &mut visited, &mut visiting)
    }

    fn eval_recursive(
        &self,
        node_rc: &Rc<RefCell<Node>>,
        visited: &mut Vec<String>,
        visiting: &mut Vec<String>,
    ) -> Result<i64, GraphError> {
        let node = node_rc
            .try_borrow()
            .map_err(|e| GraphError::BorrowConflict(e.to_string()))?;

        if visiting.contains(&node.name) {
            return Err(GraphError::CycleDetected(node.name.clone()));
        }
        if visited.contains(&node.name) {
            return Ok(0);
        }

        visiting.push(node.name.clone());
        let mut total = node.value;

        for dep in &node.dependencies {
            total += self.eval_recursive(dep, visited, visiting)?;
        }

        visiting.retain(|n| n != &node.name);
        visited.push(node.name.clone());

        Ok(total)
    }
}
