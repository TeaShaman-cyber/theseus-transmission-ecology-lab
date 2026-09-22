Module[
  {
    nodes = __NODES__, edgeData = __EDGES__, variantCount = __VARIANT_COUNT__,
    subTarget = __SUB_TARGET__, superTarget = __SUPER_TARGET__, directedEdges,
    g, b, rank, nullity, h1, h1null, index, a, k0, rho, sub, super, assoc
  },
  directedEdges = DirectedEdge @@@ edgeData[[All, {1, 2}]];
  g = Graph[nodes, directedEdges, DirectedEdges -> True];
  b = Normal[IncidenceMatrix[g]];
  rank = MatrixRank[b];
  nullity = Length[EdgeList[g]] - rank;
  h1 = Transpose[b].b;
  h1null = Length[h1] - MatrixRank[h1];
  index = AssociationThread[nodes -> Range[Length[nodes]]];
  a = ConstantArray[0, {Length[nodes], Length[nodes]}];
  Do[
    a[[index[edge[[2]]], index[edge[[1]]]]] =
      a[[index[edge[[2]]], index[edge[[1]]]]] + edge[[3]],
    {edge, edgeData}
  ];
  k0 = KroneckerProduct[a, IdentityMatrix[variantCount]];
  rho = Max[Abs[Eigenvalues[N[k0, 30]]]];
  sub = Max[Abs[Eigenvalues[N[(subTarget/rho) k0, 30]]]];
  super = Max[Abs[Eigenvalues[N[(superTarget/rho) k0, 30]]]];
  assoc = <|
    "vertex_count" -> VertexCount[g],
    "edge_count" -> EdgeCount[g],
    "weak_component_count" -> Length[WeaklyConnectedGraphComponents[g]],
    "cycle_rank_beta1" -> (
      EdgeCount[g] - VertexCount[g] + Length[WeaklyConnectedGraphComponents[g]]
    ),
    "incidence_rank" -> rank,
    "incidence_nullity" -> nullity,
    "hodge1_nullity" -> h1null,
    "base_spectral_radius" -> N[rho, 20],
    "subcritical_spectral_radius" -> N[sub, 20],
    "supercritical_spectral_radius" -> N[super, 20],
    "subcritical_below_one" -> TrueQ[sub < 1],
    "supercritical_above_one" -> TrueQ[super > 1]
  |>;
  ExportString[assoc, "RawJSON"]
]
