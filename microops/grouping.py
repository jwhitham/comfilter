
from hardware import (
        OperationList, ControlOperation, ControlLine,
    )

import typing, collections


class Vertex:
    def __init__(self, cl: ControlLine) -> None:
        self.cl = cl
        self.neighbours: VertexSet = set()

    def add_edge(self, v: "Vertex") -> None:
        self.neighbours.add(v)
        v.neighbours.add(self)

VertexSet = typing.Set[Vertex]

class BadControlError(Exception):
    pass

def grouping1(operations: OperationList) -> None:
    control_ops = [op for op in operations 
                        if isinstance(op, ControlOperation)]

    all_controls = list(ControlLine)
    all_controls.sort(key = lambda cl: cl.name)
    all_controls.remove(ControlLine.NOTHING)

    for cl in all_controls:
        for cop in control_ops:
            if cl in cop.controls:
                used = True
                break
        if not used:
            raise BadControlError(f"Control line {cl.name} is never used")

    remaining_controls = all_controls[:]
    multiplexers: typing.List[typing.List[ControlLine]] = []
    while len(remaining_controls) > 0:
        vertexes = [Vertex(cl) for cl in remaining_controls]
        for i in range(len(vertexes) - 1):
            cli = vertexes[i].cl
            for j in range(i + 1, len(vertexes)):
                clj = vertexes[j].cl
                used_together = False
                used_separately = False
                for cop in control_ops:
                    if (cli in cop.controls) or (clj in cop.controls):
                        if (cli in cop.controls) and (clj in cop.controls):
                            used_together = True
                        else:
                            used_separately = True
                if used_together and not used_separately:
                    raise BadControlError(f"Control lines {cli.name} and {clj.name} are always used together")
                elif used_separately and not used_together:
                    vertexes[i].add_edge(vertexes[j])

        maximal_clique = bron_kerbosch(set(), set(vertexes), set())
        assert maximal_clique is not None
        selected_controls = [v.cl for v in vertexes if v in maximal_clique]
        remaining_controls = [v.cl for v in vertexes if v not in maximal_clique]
        selected_controls.append(ControlLine.NOTHING)
        print(f"Multiplexer {len(multiplexers)} contains {len(selected_controls)}")
        multiplexers.append(selected_controls)
        for cl in selected_controls:
            print(f"  {cl.name}")


def bron_kerbosch(R: VertexSet, P: VertexSet, X: VertexSet) -> typing.Optional[VertexSet]:
    # https://en.wikipedia.org/wiki/Bron%E2%80%93Kerbosch_algorithm
    if len(P) == 0 and len(X) == 0:
        return R
    
    for v in P:
        maximal_clique = bron_kerbosch(R | {v}, P & v.neighbours, X & v.neighbours)
        if maximal_clique is not None:
            return maximal_clique
        P = P - {v}
        X = X | {v}
    return None

def grouping(operations: OperationList) -> None:
    control_ops = [op for op in operations 
                        if isinstance(op, ControlOperation)]
    unique: typing.Dict[str, int] = collections.defaultdict(lambda: 0)
    ignore_set = set([
        ControlLine.SHIFT_A_RIGHT, # used about 50% of the time
        ControlLine.REPEAT_FOR_ALL_BITS, # same
    ])
    #ControlLine.SET_MUX_BIT_1,
    #                ControlLine.SET_MUX_BIT_2,
    #                ControlLine.SET_MUX_BIT_4,
    #                ControlLine.SET_MUX_BIT_8])
    for cop in control_ops:
        code = ','.join(sorted(cl.name for cl in cop.controls
                        if cl not in ignore_set))
        unique[code] += 1

    frequency: typing.Dict[str, int] = collections.defaultdict(lambda: 0)
    for (i, (count, code)) in enumerate(sorted((count, code) for (code, count) in unique.items())):
        print(f"{i:2d} {count:2d} {code}")
        for name in code.split(","):
            frequency[name] += 1
    for (count, name) in sorted((count, name) for (name, count) in frequency.items()):
        print(f"-- {count:2d} {name}")

        

