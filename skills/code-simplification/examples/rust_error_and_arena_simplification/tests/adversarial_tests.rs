use rust_error_and_arena_simplification::baseline_rc_refcell::RcGraph;
use rust_error_and_arena_simplification::simplified_arena::{ArenaGraph, NodeId};

#[test]
fn test_self_loop() {
    let mut rc_g = RcGraph::new();
    let a_rc = rc_g.add_node("A", 10);
    RcGraph::add_dependency(&a_rc, &a_rc);

    let mut ar_g = ArenaGraph::new();
    let a_ar = ar_g.add_node("A", 10);
    ar_g.add_dependency(a_ar, a_ar).unwrap();

    let res_rc = rc_g.evaluate_sum(&a_rc);
    let res_ar = ar_g.evaluate_sum(a_ar);

    assert!(res_rc.is_err(), "Baseline should detect self-loop cycle");
    assert!(res_ar.is_err(), "Arena should detect self-loop cycle");
}

#[test]
fn test_mutual_cycle() {
    let mut rc_g = RcGraph::new();
    let a_rc = rc_g.add_node("A", 5);
    let b_rc = rc_g.add_node("B", 10);
    RcGraph::add_dependency(&a_rc, &b_rc);
    RcGraph::add_dependency(&b_rc, &a_rc);

    let mut ar_g = ArenaGraph::new();
    let a_ar = ar_g.add_node("A", 5);
    let b_ar = ar_g.add_node("B", 10);
    ar_g.add_dependency(a_ar, b_ar).unwrap();
    ar_g.add_dependency(b_ar, a_ar).unwrap();

    let res_rc = rc_g.evaluate_sum(&a_rc);
    let res_ar = ar_g.evaluate_sum(a_ar);

    assert!(res_rc.is_err());
    assert!(res_ar.is_err());
}

#[test]
fn test_long_cycle() {
    let mut rc_g = RcGraph::new();
    let mut rc_nodes = Vec::new();
    for i in 0..10 {
        rc_nodes.push(rc_g.add_node(&format!("N{}", i), (i + 1) * 10));
    }
    for i in 0..10 {
        RcGraph::add_dependency(&rc_nodes[i], &rc_nodes[(i + 1) % 10]);
    }

    let mut ar_g = ArenaGraph::new();
    let mut ar_nodes = Vec::new();
    for i in 0..10 {
        ar_nodes.push(ar_g.add_node(&format!("N{}", i), (i + 1) * 10));
    }
    for i in 0..10 {
        ar_g.add_dependency(ar_nodes[i], ar_nodes[(i + 1) % 10]).unwrap();
    }

    let res_rc = rc_g.evaluate_sum(&rc_nodes[0]);
    let res_ar = ar_g.evaluate_sum(ar_nodes[0]);

    assert!(res_rc.is_err());
    assert!(res_ar.is_err());
}

#[test]
fn test_cycle_with_tail() {
    let mut rc_g = RcGraph::new();
    let entry_rc = rc_g.add_node("Entry", 1);
    let t1_rc = rc_g.add_node("T1", 2);
    let t2_rc = rc_g.add_node("T2", 3);
    let c1_rc = rc_g.add_node("C1", 4);
    let c2_rc = rc_g.add_node("C2", 5);

    RcGraph::add_dependency(&entry_rc, &t1_rc);
    RcGraph::add_dependency(&t1_rc, &t2_rc);
    RcGraph::add_dependency(&t2_rc, &c1_rc);
    RcGraph::add_dependency(&c1_rc, &c2_rc);
    RcGraph::add_dependency(&c2_rc, &c1_rc);

    let mut ar_g = ArenaGraph::new();
    let entry_ar = ar_g.add_node("Entry", 1);
    let t1_ar = ar_g.add_node("T1", 2);
    let t2_ar = ar_g.add_node("T2", 3);
    let c1_ar = ar_g.add_node("C1", 4);
    let c2_ar = ar_g.add_node("C2", 5);

    ar_g.add_dependency(entry_ar, t1_ar).unwrap();
    ar_g.add_dependency(t1_ar, t2_ar).unwrap();
    ar_g.add_dependency(t2_ar, c1_ar).unwrap();
    ar_g.add_dependency(c1_ar, c2_ar).unwrap();
    ar_g.add_dependency(c2_ar, c1_ar).unwrap();

    let res_rc = rc_g.evaluate_sum(&entry_rc);
    let res_ar = ar_g.evaluate_sum(entry_ar);

    assert!(res_rc.is_err());
    assert!(res_ar.is_err());
}

#[test]
fn test_deep_linear_dag() {
    let count = 500;
    let mut rc_g = RcGraph::new();
    let mut rc_nodes = Vec::new();
    for i in 0..count {
        rc_nodes.push(rc_g.add_node(&format!("L{}", i), 1));
    }
    for i in 0..(count - 1) {
        RcGraph::add_dependency(&rc_nodes[i], &rc_nodes[i + 1]);
    }

    let mut ar_g = ArenaGraph::new();
    let mut ar_nodes = Vec::new();
    for i in 0..count {
        ar_nodes.push(ar_g.add_node(&format!("L{}", i), 1));
    }
    for i in 0..(count - 1) {
        ar_g.add_dependency(ar_nodes[i], ar_nodes[i + 1]).unwrap();
    }

    let sum_rc = rc_g.evaluate_sum(&rc_nodes[0]).unwrap();
    let sum_ar = ar_g.evaluate_sum(ar_nodes[0]).unwrap();

    assert_eq!(sum_rc, count as i64);
    assert_eq!(sum_ar, count as i64);
    assert_eq!(sum_rc, sum_ar);
}

#[test]
fn test_dense_diamond_dag() {
    let mut rc_g = RcGraph::new();
    let root_rc = rc_g.add_node("root", 100);
    let mut prev_rc = root_rc.clone();
    let mut expected_sum = 100i64;

    let mut ar_g = ArenaGraph::new();
    let root_ar = ar_g.add_node("root", 100);
    let mut prev_ar = root_ar;

    for layer in 0..10 {
        let left_name = format!("L{}_left", layer);
        let right_name = format!("L{}_right", layer);
        let bot_name = format!("L{}_bot", layer);

        let l_rc = rc_g.add_node(&left_name, 10);
        let r_rc = rc_g.add_node(&right_name, 20);
        let b_rc = rc_g.add_node(&bot_name, 30);

        RcGraph::add_dependency(&prev_rc, &l_rc);
        RcGraph::add_dependency(&prev_rc, &r_rc);
        RcGraph::add_dependency(&l_rc, &b_rc);
        RcGraph::add_dependency(&r_rc, &b_rc);
        prev_rc = b_rc;

        let l_ar = ar_g.add_node(&left_name, 10);
        let r_ar = ar_g.add_node(&right_name, 20);
        let b_ar = ar_g.add_node(&bot_name, 30);

        ar_g.add_dependency(prev_ar, l_ar).unwrap();
        ar_g.add_dependency(prev_ar, r_ar).unwrap();
        ar_g.add_dependency(l_ar, b_ar).unwrap();
        ar_g.add_dependency(r_ar, b_ar).unwrap();
        prev_ar = b_ar;

        expected_sum += 10 + 20 + 30;
    }

    let sum_rc = rc_g.evaluate_sum(&root_rc).unwrap();
    let sum_ar = ar_g.evaluate_sum(root_ar).unwrap();

    assert_eq!(sum_rc, expected_sum);
    assert_eq!(sum_ar, expected_sum);
    assert_eq!(sum_rc, sum_ar);
}

#[test]
fn test_disconnected_subgraphs() {
    let mut rc_g = RcGraph::new();
    let c1_root_rc = rc_g.add_node("C1_root", 50);
    let c1_child_rc = rc_g.add_node("C1_child", 25);
    RcGraph::add_dependency(&c1_root_rc, &c1_child_rc);

    let _c2_root_rc = rc_g.add_node("C2_root", 100);
    let _c3_isolated_rc = rc_g.add_node("C3_isolated", 200);

    let mut ar_g = ArenaGraph::new();
    let c1_root_ar = ar_g.add_node("C1_root", 50);
    let c1_child_ar = ar_g.add_node("C1_child", 25);
    ar_g.add_dependency(c1_root_ar, c1_child_ar).unwrap();

    let _c2_root_ar = ar_g.add_node("C2_root", 100);
    let _c3_isolated_ar = ar_g.add_node("C3_isolated", 200);

    let sum_rc = rc_g.evaluate_sum(&c1_root_rc).unwrap();
    let sum_ar = ar_g.evaluate_sum(c1_root_ar).unwrap();

    assert_eq!(sum_rc, 75);
    assert_eq!(sum_ar, 75);
    assert_eq!(sum_rc, sum_ar);
}

#[test]
fn test_wide_dag() {
    let mut rc_g = RcGraph::new();
    let root_rc = rc_g.add_node("wide_root", 1000);

    let mut ar_g = ArenaGraph::new();
    let root_ar = ar_g.add_node("wide_root", 1000);

    let mut expected_sum = 1000i64;
    for i in 0..500 {
        let child_name = format!("wide_child_{}", i);
        let val = (i + 1) as i64;
        let c_rc = rc_g.add_node(&child_name, val);
        RcGraph::add_dependency(&root_rc, &c_rc);

        let c_ar = ar_g.add_node(&child_name, val);
        ar_g.add_dependency(root_ar, c_ar).unwrap();
        expected_sum += val;
    }

    let sum_rc = rc_g.evaluate_sum(&root_rc).unwrap();
    let sum_ar = ar_g.evaluate_sum(root_ar).unwrap();

    assert_eq!(sum_rc, expected_sum);
    assert_eq!(sum_ar, expected_sum);
}

#[test]
fn test_invalid_node_indices() {
    let mut ar_g = ArenaGraph::new();
    let node0 = ar_g.add_node("valid_0", 10);

    let err1 = ar_g.add_dependency(node0, NodeId(999));
    assert!(err1.is_err());

    let err2 = ar_g.add_dependency(NodeId(888), node0);
    assert!(err2.is_err());

    let err3 = ar_g.evaluate_sum(NodeId(777));
    assert!(err3.is_err());
}

#[test]
fn test_single_node_negative() {
    let mut rc_g = RcGraph::new();
    let r_rc = rc_g.add_node("neg", -999);

    let mut ar_g = ArenaGraph::new();
    let r_ar = ar_g.add_node("neg", -999);

    assert_eq!(rc_g.evaluate_sum(&r_rc).unwrap(), -999);
    assert_eq!(ar_g.evaluate_sum(r_ar).unwrap(), -999);
}
